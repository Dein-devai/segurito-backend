"""Tests para backend.core.models."""
from __future__ import annotations

from backend.core.models import IntencionDef, ServiceItem, ToolDef


def test_intencion_def_defaults() -> None:
    i = IntencionDef(nombre="X", descripcion="d")
    assert i.usa_rag is True
    assert i.respuesta_fija is None


def test_intencion_def_with_respuesta_fija() -> None:
    i = IntencionDef(
        nombre="ALERTA",
        descripcion="d",
        usa_rag=False,
        respuesta_fija="texto",
    )
    assert i.usa_rag is False
    assert i.respuesta_fija == "texto"


def test_service_item_optional_similarity() -> None:
    s = ServiceItem(id="art-1", document="doc", metadata={"k": "v"})
    assert s.similarity is None


def test_tool_def_to_anthropic() -> None:
    schema = {"type": "object", "properties": {}, "required": []}
    td = ToolDef(name="t", description="d", input_schema=schema)
    a = td.to_anthropic()
    assert a == {"name": "t", "description": "d", "input_schema": schema}
