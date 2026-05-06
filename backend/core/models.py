"""Modelos de dominio compartidos entre core y plugins."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class IntencionDef(BaseModel):
    """Definición de una intención reconocida por el agente.

    Una intención puede:
    - Disparar búsqueda RAG (`usa_rag=True`).
    - Devolver una respuesta fija sin tools (`respuesta_fija != None`).
    - Solo describirse en el system prompt (caso default).
    """

    nombre: str = Field(..., description="Identificador en mayúsculas, ej. 'RECLAMO'.")
    descripcion: str = Field(..., description="Texto que el LLM ve en el system prompt.")
    usa_rag: bool = Field(default=True)
    respuesta_fija: str | None = Field(default=None)


class ServiceItem(BaseModel):
    """Resultado normalizado de búsqueda en un VectorStore.

    Cada plugin puede tener servicios con metadata distinta, pero el shape
    común incluye id, document, metadata y similarity.
    """

    id: str
    document: str
    metadata: dict[str, Any]
    similarity: float | None = None


class ToolDef(BaseModel):
    """Definición declarativa de una tool, agnóstica del transporte.

    Se traduce a Anthropic tools (HTTP) y a MCP Tool en el adapter de F4.
    """

    name: str
    description: str
    input_schema: dict[str, Any]

    def to_anthropic(self, strict: bool = True) -> dict[str, Any]:
        """Formato esperado por anthropic.messages.create(tools=[...]).

        Con strict=True fuerza al modelo a producir argumentos válidos
        según el schema, reduciendo alucinaciones en los parámetros.
        """
        schema = dict(self.input_schema)
        if strict:
            schema["additionalProperties"] = False
            # Asegurar que todos los fields estén en required
            props = schema.get("properties", {})
            if "required" not in schema:
                schema["required"] = list(props.keys())
            else:
                for prop_name in props:
                    if prop_name not in schema["required"]:
                        schema["required"].append(prop_name)
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": schema,
            **({"strict": True} if strict else {}),
        }
