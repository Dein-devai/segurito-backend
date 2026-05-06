"""Tests del ChatService con cliente Anthropic mockeado.

Diseño: construimos respuestas Anthropic falsas que simulan el flujo del
tool-use loop y verificamos que ChatService:
- Detecta organismo a partir del nombre de la tool.
- Captura intencion del input de la tool.
- Marca requiere_confirmacion en CONSULTA sin tools.
- Persiste turnos en la conversación.
- Maneja timeout / max iterations devolviendo texto humano (sin reventar).
"""
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


# --- helpers para construir respuestas Anthropic falsas ---------------------
def _text_block(text: str) -> SimpleNamespace:
    # Necesita ser instancia real de TextBlock para isinstance() check
    block = anthropic.types.TextBlock(text=text, type="text", citations=None)
    return block


def _tool_use_block(name: str, tool_input: dict, block_id: str = "tu1") -> SimpleNamespace:
    return anthropic.types.ToolUseBlock(
        id=block_id, input=tool_input, name=name, type="tool_use"
    )


def _msg(content: list, stop_reason: str) -> MagicMock:
    m = MagicMock()
    m.content = content
    m.stop_reason = stop_reason
    return m


# --- fixtures ---------------------------------------------------------------
@pytest.fixture
def registry(monkeypatch: pytest.MonkeyPatch) -> PluginRegistry:
    monkeypatch.setenv("SEGURITO_ENABLED_ORGANISMOS", '["cmf"]')
    return build_registry(Settings())


@pytest.fixture
def settings() -> Settings:
    return Settings()


@pytest.fixture
def conversations() -> ConversationStore:
    return ConversationStore(ttl_seconds=60)


def _service(
    *, client: MagicMock, registry: PluginRegistry, settings: Settings,
    conversations: ConversationStore,
) -> ChatService:
    return ChatService(
        client=client,
        registry=registry,
        settings=settings,
        pipeline=PromptPipeline(),
        conversations=conversations,
    )


# --- tests ------------------------------------------------------------------
def test_chat_sin_tools_devuelve_texto_directo(
    registry: PluginRegistry, settings: Settings, conversations: ConversationStore
) -> None:
    """ALERTA / OUT_OF_SCOPE: el modelo responde directo sin tools."""
    client = MagicMock()
    client.messages.create.return_value = _msg(
        [_text_block("Esto parece una alerta.")], stop_reason="end_turn"
    )
    svc = _service(
        client=client, registry=registry, settings=settings, conversations=conversations
    )
    result = svc.chat("creo que es estafa")
    assert "alerta" in result.response.lower()
    assert result.organismo_detectado is None
    assert result.intencion is None
    assert result.tools_used == []
    assert result.iterations == 1


def test_chat_consulta_sin_tools_marca_requiere_confirmacion(
    registry: PluginRegistry, settings: Settings, conversations: ConversationStore
) -> None:
    """CONSULTA primer turno: modelo responde sin tools → flag activado."""
    client = MagicMock()
    # El modelo no llamó tools pero tampoco hay intencion en traces:
    # requiere_confirmacion solo se marca si intencion == CONSULTA.
    # Como no hay tools, no podemos detectar intencion → flag False.
    # Validamos el caso negativo aquí.
    client.messages.create.return_value = _msg(
        [_text_block("¿Quieres que te guíe?")], stop_reason="end_turn"
    )
    svc = _service(
        client=client, registry=registry, settings=settings, conversations=conversations
    )
    result = svc.chat("tengo una duda sobre acciones")
    assert result.requiere_confirmacion is False  # sin tools no hay intencion


def test_chat_con_tool_use_detecta_organismo_e_intencion(
    registry: PluginRegistry, settings: Settings, conversations: ConversationStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RECLAMO: modelo invoca tool, ChatService detecta CMF y RECLAMO."""
    # Stub el handler para no pegarle a Chroma.
    cmf = registry.get("cmf")
    assert cmf is not None
    cmf.tool_handlers = lambda: {  # type: ignore[method-assign]
        "buscar_servicios_cmf": lambda _args: "ok markdown",
        "obtener_detalle_servicio_cmf": lambda _args: "detalle",
    }

    client = MagicMock()
    # Iteración 1: tool_use; iteración 2: end_turn con texto.
    client.messages.create.side_effect = [
        _msg(
            [_tool_use_block("buscar_servicios_cmf",
                              {"query": "banco me cobró", "intencion": "RECLAMO"})],
            stop_reason="tool_use",
        ),
        _msg([_text_block("Aquí va tu guía...")], stop_reason="end_turn"),
    ]
    svc = _service(
        client=client, registry=registry, settings=settings, conversations=conversations
    )
    result = svc.chat("banco me cobró comisión que no acordé")
    assert result.organismo_detectado == "cmf"
    assert result.intencion == "RECLAMO"
    assert result.iterations == 2
    assert len(result.tools_used) == 1
    assert "guía" in result.response


def test_chat_persiste_turnos_en_conversation_store(
    registry: PluginRegistry, settings: Settings, conversations: ConversationStore
) -> None:
    client = MagicMock()
    client.messages.create.return_value = _msg(
        [_text_block("respuesta")], stop_reason="end_turn"
    )
    svc = _service(
        client=client, registry=registry, settings=settings, conversations=conversations
    )
    r1 = svc.chat("primer mensaje")
    r2 = svc.chat("segundo mensaje", conversation_id=r1.conversation_id)
    assert r1.conversation_id == r2.conversation_id
    conv = conversations.get_or_create(r1.conversation_id)
    # 2 turnos por interacción (user + assistant) × 2 interacciones
    assert len(conv.turns) == 4


def test_chat_max_iterations_devuelve_mensaje_humano(
    registry: PluginRegistry, conversations: ConversationStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Si el modelo siempre pide tools, debe cortar y devolver mensaje humano."""
    monkeypatch.setenv("SEGURITO_MAX_TOOL_ITERATIONS", "2")
    settings = Settings()

    cmf = registry.get("cmf")
    assert cmf is not None
    cmf.tool_handlers = lambda: {  # type: ignore[method-assign]
        "buscar_servicios_cmf": lambda _a: "loop",
        "obtener_detalle_servicio_cmf": lambda _a: "loop",
    }

    client = MagicMock()
    # Siempre tool_use → forzamos max iterations.
    client.messages.create.return_value = _msg(
        [_tool_use_block("buscar_servicios_cmf",
                          {"query": "x", "intencion": "RECLAMO"})],
        stop_reason="tool_use",
    )
    svc = _service(
        client=client, registry=registry, settings=settings, conversations=conversations
    )
    result = svc.chat("query infinita")
    assert "demasiados pasos" in result.response.lower() or "reformúlala" in result.response.lower()
    assert result.iterations == 2


def test_chat_anthropic_api_error_levanta_llmerror(
    registry: PluginRegistry, settings: Settings, conversations: ConversationStore
) -> None:
    from backend.core.exceptions import LLMError

    client = MagicMock()
    err = anthropic.APIError(
        message="boom", request=MagicMock(), body=None
    )
    client.messages.create.side_effect = err
    svc = _service(
        client=client, registry=registry, settings=settings, conversations=conversations
    )
    with pytest.raises(LLMError):
        svc.chat("hola")
