"""Tests de la cascada multi-modelo en ChatService (FM3)."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import anthropic
import pytest

from backend.bootstrap import build_registry
from backend.prompt.pipeline import PromptPipeline
from backend.registry import PluginRegistry
from backend.services.chat_service import ChatService
from backend.services.conversation_store import ConversationStore
from backend.settings import Settings


def _text_block(text: str) -> anthropic.types.TextBlock:
    return anthropic.types.TextBlock(text=text, type="text", citations=None)


def _tool_use_block(
    name: str, tool_input: dict, block_id: str = "tu1"
) -> anthropic.types.ToolUseBlock:
    return anthropic.types.ToolUseBlock(
        id=block_id, input=tool_input, name=name, type="tool_use"
    )


def _msg(content: list, stop_reason: str, *, usage: dict | None = None) -> MagicMock:
    m = MagicMock()
    m.content = content
    m.stop_reason = stop_reason
    if usage is None:
        usage = {
            "input_tokens": 100,
            "output_tokens": 50,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
        }
    m.usage = SimpleNamespace(**usage)
    return m


@pytest.fixture
def registry(monkeypatch: pytest.MonkeyPatch) -> PluginRegistry:
    monkeypatch.setenv("SEGURITO_ENABLED_ORGANISMOS", '["cmf"]')
    return build_registry(Settings())


@pytest.fixture
def conversations() -> ConversationStore:
    return ConversationStore(ttl_seconds=60)


def _service(
    *,
    client: MagicMock,
    registry: PluginRegistry,
    settings: Settings,
    conversations: ConversationStore,
) -> ChatService:
    return ChatService(
        client=client,
        registry=registry,
        settings=settings,
        pipeline=PromptPipeline(),
        conversations=conversations,
    )


# --- triage --------------------------------------------------------------


def test_triage_off_no_extra_call(
    registry: PluginRegistry, conversations: ConversationStore
) -> None:
    """Con triage off (default en tests) hay 1 sola llamada al main."""
    settings = Settings()  # autouse fixture seteó enable_triage=false
    assert settings.enable_triage is False

    client = MagicMock()
    client.messages.create.return_value = _msg(
        [_text_block("ok")], stop_reason="end_turn"
    )
    svc = _service(
        client=client, registry=registry, settings=settings, conversations=conversations
    )
    result = svc.chat("hola")
    assert client.messages.create.call_count == 1
    assert len(result.reasoning) == 1
    assert result.reasoning[0].phase == "default"


def test_triage_on_ok_keeps_sonnet(
    registry: PluginRegistry,
    conversations: ConversationStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Triage responde OK → main usa Sonnet (default)."""
    monkeypatch.setenv("SEGURITO_ENABLE_TRIAGE", "true")
    settings = Settings()

    client = MagicMock()
    client.messages.create.side_effect = [
        _msg([_text_block("OK")], stop_reason="end_turn"),  # triage Haiku
        _msg([_text_block("respuesta")], stop_reason="end_turn"),  # main Sonnet
    ]
    svc = _service(
        client=client, registry=registry, settings=settings, conversations=conversations
    )
    result = svc.chat("¿qué AFP me conviene?")

    assert client.messages.create.call_count == 2
    assert len(result.reasoning) == 2
    assert result.reasoning[0].phase == "triage"
    assert result.reasoning[0].model == "claude-haiku-4-5"
    assert result.reasoning[1].phase == "default"
    assert result.reasoning[1].model == "claude-sonnet-4-5"
    assert result.model_used_final == "claude-sonnet-4-5"


def test_triage_escalate_promotes_to_opus(
    registry: PluginRegistry,
    conversations: ConversationStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Triage dice ESCALATE → main arranca en Opus desde la primera iter."""
    monkeypatch.setenv("SEGURITO_ENABLE_TRIAGE", "true")
    monkeypatch.setenv("SEGURITO_THINKING_BUDGET", "0")  # sin thinking para test
    settings = Settings()

    client = MagicMock()
    client.messages.create.side_effect = [
        _msg([_text_block("ESCALATE")], stop_reason="end_turn"),
        _msg([_text_block("respuesta legal compleja")], stop_reason="end_turn"),
    ]
    svc = _service(
        client=client, registry=registry, settings=settings, conversations=conversations
    )
    result = svc.chat("caso complicado")

    assert result.reasoning[1].phase == "escalation"
    assert result.reasoning[1].model == "claude-opus-4-6"
    assert result.model_used_final == "claude-opus-4-6"


def test_triage_failure_falls_back_to_sonnet(
    registry: PluginRegistry,
    conversations: ConversationStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Si triage explota, seguimos con Sonnet sin propagar el error."""
    monkeypatch.setenv("SEGURITO_ENABLE_TRIAGE", "true")
    settings = Settings()

    client = MagicMock()
    triage_err = anthropic.APIError(message="boom", request=MagicMock(), body=None)
    client.messages.create.side_effect = [
        triage_err,
        _msg([_text_block("respuesta sonnet")], stop_reason="end_turn"),
    ]
    svc = _service(
        client=client, registry=registry, settings=settings, conversations=conversations
    )
    result = svc.chat("query")
    assert result.response == "respuesta sonnet"
    # Triage no agregó step (falló antes de _record_step).
    assert all(s.phase != "triage" for s in result.reasoning)
    assert result.reasoning[0].phase == "default"


# --- prompt cache --------------------------------------------------------


def test_prompt_cache_disabled_sends_string_system(
    registry: PluginRegistry, conversations: ConversationStore
) -> None:
    """Con cache off, system se envía como string plano."""
    settings = Settings()
    assert settings.enable_prompt_cache is False

    client = MagicMock()
    client.messages.create.return_value = _msg(
        [_text_block("ok")], stop_reason="end_turn"
    )
    svc = _service(
        client=client, registry=registry, settings=settings, conversations=conversations
    )
    svc.chat("hola")

    kwargs = client.messages.create.call_args.kwargs
    assert isinstance(kwargs["system"], str)


def test_prompt_cache_enabled_sends_block_with_cache_control(
    registry: PluginRegistry,
    conversations: ConversationStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Con cache on, system es lista con cache_control ephemeral."""
    monkeypatch.setenv("SEGURITO_ENABLE_PROMPT_CACHE", "true")
    settings = Settings()

    client = MagicMock()
    client.messages.create.return_value = _msg(
        [_text_block("ok")], stop_reason="end_turn"
    )
    svc = _service(
        client=client, registry=registry, settings=settings, conversations=conversations
    )
    svc.chat("hola")

    kwargs = client.messages.create.call_args.kwargs
    system = kwargs["system"]
    assert isinstance(system, list)
    assert system[0]["cache_control"] == {"type": "ephemeral"}
    assert system[0]["type"] == "text"


# --- thinking + reasoning ------------------------------------------------


def test_thinking_enabled_only_on_escalation(
    registry: PluginRegistry,
    conversations: ConversationStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sólo se envía ``thinking`` cuando la decisión es escalation."""
    monkeypatch.setenv("SEGURITO_ENABLE_TRIAGE", "true")
    monkeypatch.setenv("SEGURITO_THINKING_BUDGET", "1024")
    settings = Settings()

    client = MagicMock()
    client.messages.create.side_effect = [
        _msg([_text_block("ESCALATE")], stop_reason="end_turn"),
        _msg([_text_block("ok")], stop_reason="end_turn"),
    ]
    svc = _service(
        client=client, registry=registry, settings=settings, conversations=conversations
    )
    svc.chat("caso pesado")

    triage_kwargs = client.messages.create.call_args_list[0].kwargs
    main_kwargs = client.messages.create.call_args_list[1].kwargs
    assert "thinking" not in triage_kwargs
    assert main_kwargs["thinking"] == {"type": "enabled", "budget_tokens": 1024}
    assert main_kwargs["temperature"] == 1.0


def test_reasoning_collects_usage_tokens(
    registry: PluginRegistry, conversations: ConversationStore
) -> None:
    settings = Settings()  # triage off
    client = MagicMock()
    client.messages.create.return_value = _msg(
        [_text_block("ok")],
        stop_reason="end_turn",
        usage={
            "input_tokens": 200,
            "output_tokens": 80,
            "cache_creation_input_tokens": 50,
            "cache_read_input_tokens": 30,
        },
    )
    svc = _service(
        client=client, registry=registry, settings=settings, conversations=conversations
    )
    result = svc.chat("hola")

    step = result.reasoning[0]
    assert step.input_tokens == 200
    assert step.output_tokens == 80
    assert step.cache_creation_tokens == 50
    assert step.cache_read_tokens == 30
    assert result.total_input_tokens == 200
    assert result.total_output_tokens == 80
    assert result.total_cache_creation_tokens == 50
    assert result.total_cache_read_tokens == 30


def test_iteration_threshold_escalates_inside_loop(
    registry: PluginRegistry,
    conversations: ConversationStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tras 3 iteraciones de tools, el router escala a Opus."""
    monkeypatch.setenv("SEGURITO_MAX_TOOL_ITERATIONS", "5")
    settings = Settings()  # triage off, thinking off implícito (budget>0 escalation)
    monkeypatch.setenv("SEGURITO_THINKING_BUDGET", "0")
    settings = Settings()

    cmf = registry.get("cmf")
    assert cmf is not None
    cmf.tool_handlers = lambda: {  # type: ignore[method-assign]
        "buscar_servicios_cmf": lambda _a: "ok",
        "obtener_detalle_servicio_cmf": lambda _a: "ok",
    }

    tu = lambda i: _msg(  # noqa: E731
        [
            _tool_use_block(
                "buscar_servicios_cmf",
                {"query": f"q{i}", "intencion": "RECLAMO"},
                block_id=f"tu{i}",
            )
        ],
        stop_reason="tool_use",
    )

    client = MagicMock()
    client.messages.create.side_effect = [
        tu(1),
        tu(2),
        tu(3),
        _msg([_text_block("listo")], stop_reason="end_turn"),
    ]
    svc = _service(
        client=client, registry=registry, settings=settings, conversations=conversations
    )
    result = svc.chat("query simple")

    phases = [s.phase for s in result.reasoning]
    # iter 0,1,2 → default; iter 3 → escalation.
    assert phases == ["default", "default", "default", "escalation"]
    assert result.model_used_final == "claude-opus-4-6"
