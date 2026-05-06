"""Cost tracker — convierte tokens Anthropic a USD y lleva budget diario.

Pricing (USD por millón de tokens) basado en tarifas públicas Anthropic
2025 para los modelos del cascade. Se actualiza en un solo lugar.

Reglas de cache (Anthropic):
- ``cache_creation_input_tokens``: 1.25× tarifa input.
- ``cache_read_input_tokens``: 0.10× tarifa input.

El tracker mantiene gasto diario in-memory (thread-safe). Para producción
se reemplaza por Redis/DB sin cambiar el contrato.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from threading import Lock

# USD por 1M tokens. Mantener ordenado por familia.
PRICING: dict[str, dict[str, float]] = {
    "claude-haiku-4-5": {"input": 1.0, "output": 5.0},
    "claude-sonnet-4-5": {"input": 3.0, "output": 15.0},
    "claude-opus-4-6": {"input": 15.0, "output": 75.0},
}

# Multiplicadores oficiales de prompt caching.
_CACHE_WRITE_MULT = 1.25
_CACHE_READ_MULT = 0.10
# Tarifa por defecto si el modelo no está en la tabla (conservadora = Sonnet).
_FALLBACK = {"input": 3.0, "output": 15.0}


def estimate_cost_usd(
    model: str,
    *,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_creation_tokens: int = 0,
    cache_read_tokens: int = 0,
) -> float:
    """Calcula USD para una llamada. Sin estado, fácil de testear."""
    rates = PRICING.get(model, _FALLBACK)
    cost = (
        input_tokens * rates["input"]
        + output_tokens * rates["output"]
        + cache_creation_tokens * rates["input"] * _CACHE_WRITE_MULT
        + cache_read_tokens * rates["input"] * _CACHE_READ_MULT
    )
    return cost / 1_000_000.0


@dataclass
class _DayBucket:
    day: date
    spent_usd: float = 0.0


class CostTracker:
    """Acumulador diario in-memory con budget configurable.

    No es persistente: en un reinicio se pierde el contador. Para el PoC
    es suficiente; para producción se reemplaza por backend persistente.
    """

    def __init__(self, budget_usd_per_day: float) -> None:
        self._budget = float(budget_usd_per_day)
        self._lock = Lock()
        self._bucket: _DayBucket = _DayBucket(day=date.today())

    @property
    def budget_usd_per_day(self) -> float:
        return self._budget

    def _roll(self) -> None:
        today = date.today()
        if self._bucket.day != today:
            self._bucket = _DayBucket(day=today)

    def spent_today(self) -> float:
        with self._lock:
            self._roll()
            return self._bucket.spent_usd

    def remaining_today(self) -> float:
        return max(0.0, self._budget - self.spent_today())

    def would_exceed(self, additional_usd: float) -> bool:
        return (self.spent_today() + additional_usd) > self._budget

    def record(self, cost_usd: float) -> float:
        """Registra gasto y devuelve total acumulado del día."""
        with self._lock:
            self._roll()
            self._bucket.spent_usd += max(0.0, float(cost_usd))
            return self._bucket.spent_usd


__all__ = ["PRICING", "CostTracker", "estimate_cost_usd"]
