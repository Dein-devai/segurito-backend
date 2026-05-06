"""Selector de modelo Anthropic para la cascada Haiku → Sonnet → Opus.

El ``ModelRouter`` es un componente *puro*: no realiza llamadas a la API ni
toca estado externo. Su única responsabilidad es traducir señales del turno
(mensaje del usuario, iteración del tool-loop, override explícito) en una
``RouteDecision`` con el ``model`` Anthropic a usar y la razón humana.

Reglas:
1. ``triage_model`` siempre devuelve el modelo barato (Haiku) salvo override.
2. ``main_model`` devuelve Sonnet por defecto y escala a Opus si:
   - el llamador pasa ``escalate=True`` (e.g. triage marcó alta complejidad),
   - el mensaje contiene alguna keyword de ``settings.escalation_keywords``,
   - la iteración del tool-loop supera ``escalation_iteration_threshold``.
3. ``resolve_override`` aplica overrides solo si ``allow_model_override`` está
   activo en ``Settings`` (por defecto False en producción).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from backend.settings import Settings

Phase = Literal["triage", "default", "escalation", "override"]

# Iteración del tool-loop a partir de la cual subimos a Opus si seguimos
# rebotando entre tools. Hardcodeado adrede: si necesitamos ajustarlo lo
# elevamos a Settings.
ESCALATION_ITERATION_THRESHOLD = 3


@dataclass(frozen=True)
class RouteDecision:
    """Decisión inmovible de a qué modelo enviar el turno."""

    model: str
    phase: Phase
    reason: str


class ModelRouter:
    """Decide qué modelo Anthropic usar en cada fase del turno."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        # Pre-normalizamos a lowercase para comparar barato.
        self._keywords = tuple(k.lower() for k in settings.escalation_keywords)

    # -- API pública -----------------------------------------------------

    def triage_model(self) -> RouteDecision:
        """Modelo barato para clasificación inicial / detección de scope."""
        return RouteDecision(
            model=self._settings.model_triage,
            phase="triage",
            reason="triage inicial: clasificar intención y detectar fuera de scope",
        )

    def main_model(
        self,
        user_message: str,
        *,
        iteration: int = 0,
        escalate: bool = False,
    ) -> RouteDecision:
        """Modelo principal del tool-loop con posible escalación a Opus."""
        if escalate:
            return RouteDecision(
                model=self._settings.model_escalation,
                phase="escalation",
                reason="escalación solicitada por el llamador (triage o lógica externa)",
            )

        keyword = self._match_keyword(user_message)
        if keyword is not None:
            return RouteDecision(
                model=self._settings.model_escalation,
                phase="escalation",
                reason=f"keyword de escalación detectada: '{keyword}'",
            )

        if iteration >= ESCALATION_ITERATION_THRESHOLD:
            return RouteDecision(
                model=self._settings.model_escalation,
                phase="escalation",
                reason=(
                    f"tool-loop iteración {iteration} ≥ "
                    f"{ESCALATION_ITERATION_THRESHOLD}: subimos a Opus"
                ),
            )

        return RouteDecision(
            model=self._settings.model_default,
            phase="default",
            reason="turno estándar: Sonnet maneja tool-loop",
        )

    def resolve_override(self, requested: str | None) -> RouteDecision | None:
        """Devuelve un override explícito si está permitido por settings."""
        if not requested:
            return None
        if not self._settings.allow_model_override:
            return None
        return RouteDecision(
            model=requested,
            phase="override",
            reason="override explícito (X-Force-Model) habilitado por settings",
        )

    # -- helpers internos -----------------------------------------------

    def _match_keyword(self, user_message: str) -> str | None:
        if not user_message or not self._keywords:
            return None
        haystack = user_message.lower()
        for kw in self._keywords:
            if kw and kw in haystack:
                return kw
        return None


__all__ = ["ESCALATION_ITERATION_THRESHOLD", "ModelRouter", "Phase", "RouteDecision"]
