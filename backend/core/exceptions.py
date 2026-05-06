"""Excepciones tipadas para el dominio Segurito.

Cada error tiene un tipo distinto para que los handlers HTTP puedan responder
con el código de estado correcto y mensaje apropiado.
"""
from __future__ import annotations


class SeguritoError(Exception):
    """Base de todos los errores del dominio."""


class ConfigurationError(SeguritoError):
    """Configuración faltante o inválida (ej. API key no seteada)."""


class OrganismoNotFoundError(SeguritoError):
    """Se solicitó un organismo que no está registrado."""

    def __init__(self, key: str) -> None:
        super().__init__(f"Organismo no registrado: {key!r}")
        self.key = key


class IntencionInvalidaError(SeguritoError):
    """Intención no válida para el organismo / conjunto global."""

    def __init__(self, intencion: str, validas: tuple[str, ...]) -> None:
        super().__init__(
            f"Intención inválida: {intencion!r}. Válidas: {validas}"
        )
        self.intencion = intencion
        self.validas = validas


class ToolExecutionError(SeguritoError):
    """Falla durante la ejecución de una tool del agente."""

    def __init__(self, tool_name: str, reason: str) -> None:
        super().__init__(f"Error ejecutando tool {tool_name!r}: {reason}")
        self.tool_name = tool_name
        self.reason = reason


class LLMError(SeguritoError):
    """Falla en la comunicación o respuesta del LLM."""


class ToolLoopTimeoutError(SeguritoError):
    """El bucle agentic excedió el tiempo máximo permitido."""


class ToolLoopMaxIterationsError(SeguritoError):
    """El bucle agentic excedió el máximo de iteraciones."""
