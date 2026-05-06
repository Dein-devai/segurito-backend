"""Tests para backend.services.cost_tracker."""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from backend.services.cost_tracker import (
    PRICING,
    CostTracker,
    estimate_cost_usd,
)


def test_estimate_cost_haiku_basic() -> None:
    cost = estimate_cost_usd(
        "claude-haiku-4-5", input_tokens=1_000_000, output_tokens=0
    )
    assert cost == pytest.approx(PRICING["claude-haiku-4-5"]["input"])


def test_estimate_cost_sonnet_input_plus_output() -> None:
    cost = estimate_cost_usd(
        "claude-sonnet-4-5", input_tokens=1_000_000, output_tokens=1_000_000
    )
    assert cost == pytest.approx(
        PRICING["claude-sonnet-4-5"]["input"]
        + PRICING["claude-sonnet-4-5"]["output"]
    )


def test_estimate_cost_cache_write_125x() -> None:
    cost = estimate_cost_usd(
        "claude-sonnet-4-5", cache_creation_tokens=1_000_000
    )
    assert cost == pytest.approx(PRICING["claude-sonnet-4-5"]["input"] * 1.25)


def test_estimate_cost_cache_read_010x() -> None:
    cost = estimate_cost_usd(
        "claude-sonnet-4-5", cache_read_tokens=1_000_000
    )
    assert cost == pytest.approx(PRICING["claude-sonnet-4-5"]["input"] * 0.10)


def test_estimate_cost_unknown_model_uses_fallback() -> None:
    cost = estimate_cost_usd("modelo-fantasma-9", input_tokens=1_000_000)
    assert cost == pytest.approx(3.0)  # tarifa Sonnet de fallback


def test_tracker_records_and_accumulates() -> None:
    t = CostTracker(budget_usd_per_day=10.0)
    assert t.spent_today() == 0.0
    t.record(2.5)
    t.record(1.5)
    assert t.spent_today() == pytest.approx(4.0)
    assert t.remaining_today() == pytest.approx(6.0)


def test_tracker_would_exceed() -> None:
    t = CostTracker(budget_usd_per_day=10.0)
    t.record(7.0)
    assert t.would_exceed(2.0) is False
    assert t.would_exceed(5.0) is True


def test_tracker_negative_cost_clamped_to_zero() -> None:
    t = CostTracker(budget_usd_per_day=10.0)
    t.record(-100.0)
    assert t.spent_today() == 0.0


def test_tracker_rolls_on_new_day(monkeypatch: pytest.MonkeyPatch) -> None:
    t = CostTracker(budget_usd_per_day=10.0)
    t.record(5.0)

    # Simula que pasa el día: parchamos date.today() en el módulo.
    yesterday = date.today() - timedelta(days=1)
    t._bucket.day = yesterday  # type: ignore[attr-defined]
    assert t.spent_today() == 0.0  # bucket fue rolleado


def test_budget_property_exposed() -> None:
    t = CostTracker(budget_usd_per_day=42.5)
    assert t.budget_usd_per_day == 42.5
