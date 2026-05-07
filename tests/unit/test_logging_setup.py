"""Tests para backend.logging_setup."""
from __future__ import annotations

import logging

from backend.logging_setup import configure_logging, get_logger


def test_configure_logging_sets_root_level() -> None:
    configure_logging("DEBUG")
    assert logging.getLogger().level == logging.DEBUG


def test_configure_logging_is_idempotent() -> None:
    """Llamar dos veces no duplica handlers."""
    # Resetea el flag de módulo
    import backend.logging_setup as m
    m._CONFIGURED = False
    logging.getLogger().handlers.clear()

    configure_logging("INFO")
    handlers_after_first = len(logging.getLogger().handlers)

    configure_logging("INFO")
    handlers_after_second = len(logging.getLogger().handlers)

    assert handlers_after_first == handlers_after_second


def test_get_logger_returns_named_logger() -> None:
    log = get_logger("my.module")
    assert log.name == "my.module"


def test_noisy_libs_are_silenced() -> None:
    import backend.logging_setup as m
    m._CONFIGURED = False
    logging.getLogger().handlers.clear()

    configure_logging("DEBUG")

    assert logging.getLogger("httpx").level == logging.WARNING
    assert logging.getLogger("psycopg").level == logging.WARNING
