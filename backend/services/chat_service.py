"""ChatService — orquesta la cascada Haiku → Sonnet → Opus con tool-use.

FM3:
- Triage opcional (Haiku) decide escalación temprana.
- Tool-loop principal usa modelo del ``ModelRouter`` por iteración (Sonnet
  por defecto, Opus si triage marcó ``ESCALATE`` / hay keyword sensible /
  iteración ≥ umbral).
- Anthropic prompt caching (``cache_control: ephemeral``) en el system
  prompt cuando ``settings.enable_prompt_cache``.
- Extended thinking en escalación si ``settings.thinking_budget_tokens > 0``.
- Recolección de ``ReasoningStep`` por cada llamada a la API (auditable).
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import anthropic
from anthropic.types import (
    Message,
    TextBlock,
    ThinkingBlock,
    ToolUseBlock,
)

from backend.api.schemas import ChatResponse, ReasoningStep, ToolTrace
from backend.core.exceptions import (
    LLMError,
    ToolLoopMaxIterationsError,
    ToolLoopTimeoutError,
)
from backend.logging_setup import get_logger
from backend.prompt.pipeline import PromptPipeline
from backend.registry import PluginRegistry
from backend.services.conversation_store import ConversationStore
from backend.services.cost_tracker import CostTracker, estimate_cost_usd
from backend.services.model_router import ModelRouter, RouteDecision
from backend.services.rate_limiter import RateLimiter
from backend.settings import Settings

log = get_logger(__name__)

_MSG_TIMEOUT = (
    "Lo siento, tu consulta tardó más de lo esperado en procesarse. "
    "Intenta nuevamente con una pregunta más directa."
)
_MSG_MAX_ITER = (
    "Tu consulta requirió demasiados pasos para resolverse. Por favor reformúlala "
    "indicando con claridad el problema concreto que tienes."
)

_TRIAGE_SYSTEM = (
    "Eres un clasificador rápido de consultas ciudadanas a organismos del "
    "Estado de Chile (CMF, SERNAC, SII, marco legal). Tu única tarea es "
    "decidir si la consulta requiere razonamiento legal complejo, involucra "
    "acciones legales (demanda, querella, fraude grave, información "
    "privilegiada) o ambigüedad cross-organismo no resoluble con tools "
    "estándar.\n\n"
    "Responde EXACTAMENTE una palabra:\n"
    "- ESCALATE  si el caso requiere Opus.\n"
    "- OK        si Sonnet basta."
)
_TRIAGE_MAX_TOKENS = 16


@dataclass
class _LoopOutcome:
    text: str
    tools_used: list[ToolTrace]
    iterations: int
    reasoning: list[ReasoningStep] = field(default_factory=list)
    final_model: str | None = None


class ChatService:
    """Caso de uso principal: una vuelta de chat con cascada multi-modelo."""

    def __init__(
        self,
        client: anthropic.Anthropic,
        registry: PluginRegistry,
        settings: Settings,
        pipeline: PromptPipeline,
        conversations: ConversationStore,
        router: ModelRouter | None = None,
        rate_limiter: RateLimiter | None = None,
        cost_tracker: CostTracker | None = None,
    ) -> None:
        self._client = client
        self._registry = registry
        self._settings = settings
        self._pipeline = pipeline
        self._conversations = conversations
        self._router = router or ModelRouter(settings)
        self._rate_limiter = rate_limiter
        self._cost_tracker = cost_tracker

    # --- helpers ----------------------------------------------------------
    @staticmethod
    def _extract_text(message: Message) -> str:
        parts = [b.text for b in message.content if isinstance(b, TextBlock)]
        return "\n".join(p.strip() for p in parts if p).strip()

    @staticmethod
    def _extract_thinking(message: Message) -> str | None:
        parts = [b.thinking for b in message.content if isinstance(b, ThinkingBlock)]
        joined = "\n".join(p for p in parts if p).strip()
        return joined or None

    def _detect_organismo(self, tool_name: str) -> str | None:
        for plugin in self._registry.all_plugins():
            if any(t.name == tool_name for t in plugin.tools()):
                return plugin.key
        return None

    @staticmethod
    def _extract_intencion(traces: list[ToolTrace]) -> str | None:
        for t in traces:
            intencion = t.input.get("intencion")
            if isinstance(intencion, str):
                return intencion.upper()
        return None

    def _build_system(self, system_prompt: str) -> Any:
        """Devuelve system como string o lista de bloques con cache_control."""
        if not self._settings.enable_prompt_cache:
            return system_prompt
        return [
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ]

    @staticmethod
    def _usage_field(usage: Any, name: str) -> int:
        value = getattr(usage, name, 0)
        return int(value) if isinstance(value, int) else 0

    def _record_step(
        self,
        decision: RouteDecision,
        response: Message,
        elapsed_ms: int,
    ) -> ReasoningStep:
        usage = getattr(response, "usage", None)
        in_tok = self._usage_field(usage, "input_tokens")
        out_tok = self._usage_field(usage, "output_tokens")
        cache_read = self._usage_field(usage, "cache_read_input_tokens")
        cache_create = self._usage_field(usage, "cache_creation_input_tokens")
        cost = estimate_cost_usd(
            decision.model,
            input_tokens=in_tok,
            output_tokens=out_tok,
            cache_creation_tokens=cache_create,
            cache_read_tokens=cache_read,
        )
        if self._cost_tracker is not None:
            self._cost_tracker.record(cost)
        return ReasoningStep(
            model=decision.model,
            phase=decision.phase,
            reason=decision.reason,
            thinking=self._extract_thinking(response),
            elapsed_ms=elapsed_ms,
            input_tokens=in_tok,
            output_tokens=out_tok,
            cache_read_tokens=cache_read,
            cache_creation_tokens=cache_create,
            cost_usd=cost,
        )

    # --- triage -----------------------------------------------------------
    def _run_triage(self, user_message: str) -> tuple[bool, ReasoningStep | None]:
        """Llama a Haiku y devuelve (escalate, step). Falla → no escala."""
        if not self._settings.enable_triage:
            return False, None

        decision = self._router.triage_model()
        started = time.monotonic()
        try:
            response = self._client.messages.create(
                model=decision.model,
                max_tokens=_TRIAGE_MAX_TOKENS,
                system=_TRIAGE_SYSTEM,
                messages=[{"role": "user", "content": user_message}],
            )
        except anthropic.APIError as exc:
            log.warning("triage falló (%s); continúo sin escalación", exc)
            return False, None
        elapsed = int((time.monotonic() - started) * 1000)
        step = self._record_step(decision, response, elapsed)
        text = self._extract_text(response).upper()
        escalate = "ESCALATE" in text
        log.info(
            "triage decision=%s text=%r", "ESCALATE" if escalate else "OK", text
        )
        return escalate, step

    # --- core loop --------------------------------------------------------
    def _call_main(
        self,
        decision: RouteDecision,
        system: Any,
        anth_tools: list[dict[str, Any]],
        messages: list[dict[str, Any]],
    ) -> tuple[Message, int]:
        """Llamada al modelo principal con thinking si aplica a Opus."""
        kwargs: dict[str, Any] = {
            "model": decision.model,
            "max_tokens": 2048,
            "system": system,
            "tools": anth_tools,
            "messages": messages,
        }
        if (
            decision.phase == "escalation"
            and self._settings.thinking_budget_tokens > 0
        ):
            kwargs["max_tokens"] = max(
                4096, self._settings.thinking_budget_tokens + 1024
            )
            kwargs["thinking"] = {
                "type": "enabled",
                "budget_tokens": self._settings.thinking_budget_tokens,
            }
            # Extended thinking exige temperature=1.
            kwargs["temperature"] = 1.0

        started = time.monotonic()
        try:
            response = self._client.messages.create(**kwargs)
        except anthropic.APIError as exc:
            raise LLMError(f"Anthropic API error: {exc}") from exc
        elapsed = int((time.monotonic() - started) * 1000)
        return response, elapsed

    def _run_loop(
        self,
        user_message: str,
        history: list[dict[str, Any]],
        system_prompt: str,
        anth_tools: list[dict[str, Any]],
        triage_escalate: bool,
        reasoning: list[ReasoningStep],
        conversation_id: str | None = None,
    ) -> _LoopOutcome:
        wrapped = f"<user_input>\n{user_message}\n</user_input>"
        messages: list[dict[str, Any]] = list(history) + [
            {"role": "user", "content": wrapped}
        ]
        traces: list[ToolTrace] = []
        started = time.monotonic()
        max_iter = self._settings.max_tool_iterations
        timeout_s = self._settings.tool_loop_timeout_s
        system = self._build_system(system_prompt)
        last_model: str | None = None

        for iteration in range(1, max_iter + 1):
            if time.monotonic() - started > timeout_s:
                log.warning("tool loop timeout after %ss", timeout_s)
                raise ToolLoopTimeoutError()

            decision = self._router.main_model(
                user_message,
                iteration=iteration - 1,
                escalate=triage_escalate,
            )
            if self._rate_limiter is not None:
                self._rate_limiter.check_model(decision.model, conversation_id)
            response, elapsed = self._call_main(
                decision, system, anth_tools, messages
            )
            reasoning.append(self._record_step(decision, response, elapsed))
            last_model = decision.model

            if response.stop_reason != "tool_use":
                return _LoopOutcome(
                    text=self._extract_text(response),
                    tools_used=traces,
                    iterations=iteration,
                    reasoning=reasoning,
                    final_model=last_model,
                )

            messages.append({"role": "assistant", "content": response.content})

            tool_results: list[dict[str, Any]] = []
            for block in response.content:
                if not isinstance(block, ToolUseBlock):
                    continue
                traces.append(ToolTrace(name=block.name, input=dict(block.input)))
                tool_text = self._registry.execute_tool(
                    block.name, dict(block.input)
                )
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": tool_text,
                    }
                )

            if not tool_results:
                return _LoopOutcome(
                    text=self._extract_text(response),
                    tools_used=traces,
                    iterations=iteration,
                    reasoning=reasoning,
                    final_model=last_model,
                )

            messages.append({"role": "user", "content": tool_results})

        log.warning("max iterations (%s) reached", max_iter)
        raise ToolLoopMaxIterationsError()

    # --- public API -------------------------------------------------------
    def chat(
        self, message: str, conversation_id: str | None = None
    ) -> ChatResponse:
        interaction_id = str(uuid.uuid4())
        started = time.monotonic()
        conv = self._conversations.get_or_create(conversation_id)

        system_prompt = self._pipeline.build(self._registry)
        anth_tools = [t.to_anthropic() for t in self._registry.all_tools()]
        history = [
            {"role": turn.role, "content": turn.content} for turn in conv.turns
        ]

        reasoning: list[ReasoningStep] = []
        triage_escalate, triage_step = self._run_triage(message)
        if triage_step is not None:
            reasoning.append(triage_step)

        try:
            outcome = self._run_loop(
                message,
                history,
                system_prompt,
                anth_tools,
                triage_escalate=triage_escalate,
                reasoning=reasoning,
                conversation_id=conv.id,
            )
        except ToolLoopTimeoutError:
            outcome = _LoopOutcome(
                text=_MSG_TIMEOUT,
                tools_used=[],
                iterations=0,
                reasoning=reasoning,
            )
        except ToolLoopMaxIterationsError:
            outcome = _LoopOutcome(
                text=_MSG_MAX_ITER,
                tools_used=[],
                iterations=self._settings.max_tool_iterations,
                reasoning=reasoning,
            )

        # Persistir turnos en la conversación (para próximos turnos de CONSULTA).
        self._conversations.append_turn(
            conv.id, "user", f"<user_input>\n{message}\n</user_input>"
        )
        self._conversations.append_turn(conv.id, "assistant", outcome.text)

        organismo = None
        servicio_id = None
        servicios: list[str] = []
        for trace in outcome.tools_used:
            if organismo is None:
                organismo = self._detect_organismo(trace.name)
            if "service_id" in trace.input:
                servicio_id = str(trace.input["service_id"])
            if "query" in trace.input:
                servicios.append(str(trace.input["query"]))

        elapsed_ms = int((time.monotonic() - started) * 1000)
        intencion = self._extract_intencion(outcome.tools_used)
        requiere_confirmacion = intencion == "CONSULTA" and not outcome.tools_used

        total_in = sum(s.input_tokens for s in outcome.reasoning)
        total_out = sum(s.output_tokens for s in outcome.reasoning)
        total_cache_read = sum(s.cache_read_tokens for s in outcome.reasoning)
        total_cache_create = sum(s.cache_creation_tokens for s in outcome.reasoning)
        total_cost = sum(s.cost_usd for s in outcome.reasoning)

        return ChatResponse(
            interaction_id=interaction_id,
            conversation_id=conv.id,
            response=outcome.text,
            organismo_detectado=organismo,
            intencion=intencion,
            servicio_id=servicio_id,
            servicios_encontrados=servicios,
            requiere_confirmacion=requiere_confirmacion,
            tools_used=outcome.tools_used,
            iterations=outcome.iterations,
            elapsed_ms=elapsed_ms,
            reasoning=outcome.reasoning,
            model_used_final=outcome.final_model,
            total_input_tokens=total_in,
            total_output_tokens=total_out,
            total_cache_read_tokens=total_cache_read,
            total_cache_creation_tokens=total_cache_create,
            total_cost_usd=total_cost,
        )


__all__ = ["ChatService"]
