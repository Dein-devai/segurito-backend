"""Configuración centralizada de logging.

Un único punto donde se define formato y nivel; el resto del código solo
hace `log = logging.getLogger(__name__)`.
"""
from __future__ import annotations

import logging
import sys

_CONFIGURED = False


def configure_logging(level: str = "INFO") -> None:
    """Configura el root logger. Re-aplica el nivel si ya estaba configurado."""
    global _CONFIGURED
    root = logging.getLogger()

    if _CONFIGURED:
        root.setLevel(level.upper())
        return

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())

    # Silenciar libs ruidosas
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("psycopg").setLevel(logging.WARNING)
    logging.getLogger("psycopg.pool").setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Helper conveniente."""
    return logging.getLogger(name)
