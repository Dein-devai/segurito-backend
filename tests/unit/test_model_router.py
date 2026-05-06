"""Tests para backend.services.model_router (FM2)."""
from __future__ import annotations

import pytest

from backend.services.model_router import (
    ESCALATION_ITERATION_THRESHOLD,
    ModelRouter,
    RouteDecision,
)


@pytest.fixture
def router(fresh_settings) -> ModelRouter:
    return ModelRouter(fresh_settings)


def test_triage_returns_haiku(router: ModelRouter, fresh_settings) -> None:
    decision = router.triage_model()
    assert isinstance(decision, RouteDecision)
    assert decision.model == fresh_settings.model_triage
    assert decision.model == "claude-haiku-4-5"
    assert decision.phase == "triage"
    assert "triage" in decision.reason.lower()


def test_main_default_returns_sonnet(router: ModelRouter, fresh_settings) -> None:
    decision = router.main_model("¿qué AFP me conviene?", iteration=0)
    assert decision.model == fresh_settings.model_default
    assert decision.model == "claude-sonnet-4-5"
    assert decision.phase == "default"


def test_main_explicit_escalate_overrides(router: ModelRouter, fresh_settings) -> None:
    decision = router.main_model("hola", iteration=0, escalate=True)
    assert decision.model == fresh_settings.model_escalation
    assert decision.phase == "escalation"
    assert "llamador" in decision.reason.lower() or "solicitada" in decision.reason.lower()


def test_main_keyword_triggers_escalation(router: ModelRouter, fresh_settings) -> None:
    decision = router.main_model(
        "Quiero presentar una DEMANDA contra mi banco", iteration=0
    )
    assert decision.model == fresh_settings.model_escalation
    assert decision.phase == "escalation"
    assert "demanda" in decision.reason.lower()


def test_main_keyword_case_insensitive(router: ModelRouter) -> None:
    decision = router.main_model("información PRIVILEGIADA usada en el mercado")
    assert decision.phase == "escalation"
    assert "privilegiada" in decision.reason.lower()


def test_main_iteration_threshold_escalates(router: ModelRouter, fresh_settings) -> None:
    decision = router.main_model(
        "consulta simple", iteration=ESCALATION_ITERATION_THRESHOLD
    )
    assert decision.model == fresh_settings.model_escalation
    assert decision.phase == "escalation"
    assert "iteración" in decision.reason.lower() or "iteracion" in decision.reason.lower()


def test_main_iteration_below_threshold_stays_default(
    router: ModelRouter, fresh_settings
) -> None:
    decision = router.main_model(
        "consulta simple", iteration=ESCALATION_ITERATION_THRESHOLD - 1
    )
    assert decision.model == fresh_settings.model_default
    assert decision.phase == "default"


def test_main_empty_message_no_keyword_match(router: ModelRouter, fresh_settings) -> None:
    decision = router.main_model("", iteration=0)
    assert decision.model == fresh_settings.model_default
    assert decision.phase == "default"


def test_resolve_override_disabled_by_default(router: ModelRouter) -> None:
    assert router.resolve_override("claude-opus-4-6") is None


def test_resolve_override_none_input(router: ModelRouter) -> None:
    assert router.resolve_override(None) is None


def test_resolve_override_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SEGURITO_ALLOW_MODEL_OVERRIDE", "true")
    from backend.settings import get_settings
    get_settings.cache_clear()
    settings = get_settings()
    router = ModelRouter(settings)

    decision = router.resolve_override("claude-opus-4-6")
    assert decision is not None
    assert decision.model == "claude-opus-4-6"
    assert decision.phase == "override"


def test_resolve_override_enabled_but_empty_string(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SEGURITO_ALLOW_MODEL_OVERRIDE", "true")
    from backend.settings import get_settings
    get_settings.cache_clear()
    router = ModelRouter(get_settings())

    assert router.resolve_override("") is None


def test_route_decision_is_frozen() -> None:
    d = RouteDecision(model="x", phase="default", reason="r")
    with pytest.raises(Exception):  # FrozenInstanceError
        d.model = "y"  # type: ignore[misc]


def test_priority_explicit_escalate_over_default_iteration(
    router: ModelRouter, fresh_settings
) -> None:
    """escalate=True gana incluso con iteración baja y mensaje sin keyword."""
    decision = router.main_model("hola", iteration=0, escalate=True)
    assert decision.phase == "escalation"
    assert decision.model == fresh_settings.model_escalation
