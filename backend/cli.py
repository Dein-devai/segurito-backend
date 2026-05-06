"""CLI para Segurito.

Uso:
    python -m backend.cli                                 # modo interactivo (REPL)
    python -m backend.cli "¿Cómo reclamo a mi banco?"     # one-shot
    python -m backend.cli --no-thinking "consulta"
    python -m backend.cli --force-model claude-opus-4-6 "consulta"

En modo interactivo: escribe consultas y enter; ``exit``, ``quit``, ``salir``
o ``:q`` terminan la sesión (también EOF: Ctrl+Z+Enter en Windows / Ctrl+D en
Unix; o Ctrl+C). ``:reset`` empieza una nueva conversación sin salir del REPL.
Imprime la cascada multi-modelo paso a paso (triage → main → escalación)
con tokens, costo USD por step y respuesta final.
"""
from __future__ import annotations

import os

# Embeddings cacheados localmente por sentence-transformers en
# ~/.cache/huggingface/. Forzamos modo offline ANTES de importar cualquier
# cosa que arrastre transformers/HF para evitar HEAD a HF Hub que cuelga
# cuando hay red lenta o sin internet. ``setdefault`` permite re-descargar
# exportando ``HF_HUB_OFFLINE=0`` antes de invocar el CLI.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

import argparse  # noqa: E402
import sys  # noqa: E402
from typing import Any  # noqa: E402

from backend.api.dependencies import (
    get_anthropic_dep,
    get_conversation_store_dep,
    get_pipeline_dep,
    get_registry_dep,
)
from backend.services.chat_service import ChatService
from backend.services.cost_tracker import CostTracker
from backend.services.model_router import ModelRouter
from backend.services.rate_limiter import RateLimiter
from backend.settings import get_settings

# Colores ANSI básicos. Si la terminal no los soporta, no rompe nada.
_C = {
    "reset": "\033[0m",
    "dim": "\033[2m",
    "bold": "\033[1m",
    "cyan": "\033[36m",
    "yellow": "\033[33m",
    "green": "\033[32m",
    "magenta": "\033[35m",
    "red": "\033[31m",
}


def _color(name: str, text: str) -> str:
    if os.environ.get("NO_COLOR"):
        return text
    return f"{_C[name]}{text}{_C['reset']}"


def _phase_color(phase: str) -> str:
    return {
        "triage": "cyan",
        "default": "green",
        "escalation": "magenta",
        "override": "yellow",
    }.get(phase, "dim")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="segurito",
        description="CLI Segurito — chat con cascada Haiku→Sonnet→Opus.",
    )
    p.add_argument(
        "query",
        nargs="?",
        default=None,
        help="Mensaje del ciudadano. Si se omite, abre REPL interactivo.",
    )
    p.add_argument(
        "--no-thinking",
        action="store_true",
        help="Desactiva extended thinking en escalación.",
    )
    p.add_argument(
        "--force-model",
        default=None,
        help=(
            "Fuerza un modelo Anthropic concreto (requiere "
            "SEGURITO_ALLOW_MODEL_OVERRIDE=true)."
        ),
    )
    p.add_argument(
        "--no-cache",
        action="store_true",
        help="Desactiva Anthropic prompt caching.",
    )
    p.add_argument(
        "--conversation-id",
        default=None,
        help="Continúa una conversación existente.",
    )
    return p


def _print_step(step: Any, idx: int) -> None:
    color = _phase_color(step.phase)
    header = _color(color, f"[{idx}] {step.phase.upper()} · {step.model}")
    print(header)
    print(_color("dim", f"    razón:    {step.reason}"))
    print(
        _color(
            "dim",
            f"    tokens:   in={step.input_tokens} out={step.output_tokens} "
            f"cache_r={step.cache_read_tokens} cache_w={step.cache_creation_tokens}",
        )
    )
    print(_color("dim", f"    cost:     ${step.cost_usd:.6f}"))
    print(_color("dim", f"    elapsed:  {step.elapsed_ms} ms"))
    if step.thinking:
        thinking_short = step.thinking[:200] + (
            "…" if len(step.thinking) > 200 else ""
        )
        print(_color("yellow", f"    thinking: {thinking_short}"))


def _run_turn(
    service: ChatService, query: str, conversation_id: str | None
) -> tuple[str, float]:
    """Ejecuta un turno y lo imprime. Devuelve ``(conversation_id, cost_usd)``."""
    print(_color("bold", f"\n› {query}\n"))
    result = service.chat(query, conversation_id=conversation_id)

    print(_color("bold", "── Cascada ──"))
    for i, step in enumerate(result.reasoning, start=1):
        _print_step(step, i)
    print()

    print(_color("bold", "── Respuesta ──"))
    print(result.response)
    print()

    summary = (
        f"organismo={result.organismo_detectado}  "
        f"intencion={result.intencion}  "
        f"iter={result.iterations}  "
        f"elapsed={result.elapsed_ms}ms  "
        f"cost=${result.total_cost_usd:.6f}  "
        f"conv={result.conversation_id}"
    )
    print(_color("dim", summary))
    return result.conversation_id, result.total_cost_usd


_EXIT_COMMANDS = {"exit", "quit", "salir", ":q"}


def _run_repl(service: ChatService, conversation_id: str | None) -> int:
    """Loop interactivo. Termina con exit/quit/salir/:q, EOF o Ctrl+C."""
    print(_color("bold", "Segurito CLI — modo interactivo"))
    print(
        _color(
            "dim",
            "Escribe tu consulta y enter. Comandos: 'exit'/'quit'/'salir'/':q' "
            "para salir, ':reset' para nueva conversación.",
        )
    )
    total_cost = 0.0
    turns = 0
    while True:
        try:
            raw = input(_color("bold", "\n› "))
        except (EOFError, KeyboardInterrupt):
            print()
            break

        msg = raw.strip()
        if not msg:
            continue
        if msg.lower() in _EXIT_COMMANDS:
            break
        if msg.lower() == ":reset":
            conversation_id = None
            print(_color("dim", "  (nueva conversación)"))
            continue

        try:
            conversation_id, cost = _run_turn(service, msg, conversation_id)
        except Exception as exc:  # noqa: BLE001 — REPL no muere por un turno
            print(_color("red", f"ERROR: {exc}"), file=sys.stderr)
            continue
        total_cost += cost
        turns += 1

    print(
        _color(
            "dim",
            f"Hasta pronto. turnos={turns} cost_total=${total_cost:.6f}",
        )
    )
    return 0


def _check_runtime_deps() -> str | None:
    """Verifica deps críticas. Devuelve mensaje de error o None.

    El error típico ``No module named 'chromadb'`` aparece dentro del tool-call
    y confunde porque el CLI ya arrancó. Lo capturamos al inicio para abortar
    rápido con instrucciones útiles (probable causa: venv no activado).
    """
    missing = []
    for mod in ("chromadb", "sentence_transformers"):
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    if not missing:
        return None
    return (
        f"ERROR: faltan dependencias: {', '.join(missing)}.\n"
        f"  Probable causa: venv no activado. Usá:\n"
        f"    .\\.venv\\Scripts\\python.exe -m backend.cli   (Windows)\n"
        f"    .venv/bin/python -m backend.cli                (Unix)\n"
        f"  O activá el venv y luego corré pip install -r requirements.txt."
    )


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    dep_error = _check_runtime_deps()
    if dep_error:
        print(_color("red", dep_error), file=sys.stderr)
        return 2

    if args.no_thinking:
        os.environ["SEGURITO_THINKING_BUDGET"] = "0"
    if args.no_cache:
        os.environ["SEGURITO_ENABLE_PROMPT_CACHE"] = "false"

    get_settings.cache_clear()
    settings = get_settings()

    if not settings.anthropic_api_key:
        print(_color("red", "ERROR: ANTHROPIC_API_KEY no configurada"), file=sys.stderr)
        return 2

    router = ModelRouter(settings)
    if args.force_model:
        override = router.resolve_override(args.force_model)
        if override is None:
            print(
                _color(
                    "red",
                    "ERROR: --force-model requiere SEGURITO_ALLOW_MODEL_OVERRIDE=true",
                ),
                file=sys.stderr,
            )
            return 2

    service = ChatService(
        client=get_anthropic_dep(),
        registry=get_registry_dep(),
        settings=settings,
        pipeline=get_pipeline_dep(),
        conversations=get_conversation_store_dep(),
        router=router,
        rate_limiter=RateLimiter(settings),
        cost_tracker=CostTracker(settings.cost_budget_usd_per_day),
    )

    if args.query is None:
        return _run_repl(service, args.conversation_id)

    _run_turn(service, args.query, args.conversation_id)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
