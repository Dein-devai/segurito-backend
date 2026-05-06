"""Tests para backend.cli."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import anthropic
import pytest

from backend import cli


def _msg(text: str) -> MagicMock:
    m = MagicMock()
    m.content = [anthropic.types.TextBlock(text=text, type="text", citations=None)]
    m.stop_reason = "end_turn"
    m.usage = SimpleNamespace(
        input_tokens=10,
        output_tokens=5,
        cache_creation_input_tokens=0,
        cache_read_input_tokens=0,
    )
    return m


@pytest.fixture
def mock_anthropic(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Reemplaza el cliente Anthropic global por uno mockeado."""
    client = MagicMock()
    client.messages.create.return_value = _msg("respuesta")

    from backend.api import dependencies

    monkeypatch.setattr(dependencies, "get_anthropic_dep", lambda: client)
    monkeypatch.setattr(cli, "get_anthropic_dep", lambda: client)
    return client


def test_cli_basic_query(
    mock_anthropic: MagicMock,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SEGURITO_ENABLED_ORGANISMOS", '["cmf"]')
    monkeypatch.setenv("SEGURITO_ENABLE_TRIAGE", "false")

    rc = cli.main(["test query"])
    assert rc == 0

    out = capsys.readouterr().out
    assert "Cascada" in out
    assert "Respuesta" in out
    assert "respuesta" in out
    assert "DEFAULT" in out  # phase mostrada


def test_cli_no_api_key_returns_2(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    rc = cli.main(["query"])
    assert rc == 2
    err = capsys.readouterr().err
    assert "ANTHROPIC_API_KEY" in err


def test_cli_force_model_without_permission_returns_2(
    mock_anthropic: MagicMock,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SEGURITO_ALLOW_MODEL_OVERRIDE", "false")
    rc = cli.main(["--force-model", "claude-opus-4-6", "query"])
    assert rc == 2
    assert "SEGURITO_ALLOW_MODEL_OVERRIDE" in capsys.readouterr().err


def test_cli_no_thinking_flag_sets_env(
    mock_anthropic: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SEGURITO_ENABLED_ORGANISMOS", '["cmf"]')
    monkeypatch.setenv("SEGURITO_ENABLE_TRIAGE", "false")
    monkeypatch.setenv("SEGURITO_THINKING_BUDGET", "2048")

    cli.main(["--no-thinking", "query"])
    # El flag debió haber sobreescrito el env.
    import os
    assert os.environ["SEGURITO_THINKING_BUDGET"] == "0"


def test_cli_argparse_help(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["--help"])
    assert exc.value.code == 0


def test_cli_repl_exits_on_command(
    mock_anthropic: MagicMock,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sin query posicional → REPL. 'exit' termina sin invocar al LLM."""
    monkeypatch.setenv("SEGURITO_ENABLED_ORGANISMOS", '["cmf"]')
    monkeypatch.setenv("SEGURITO_ENABLE_TRIAGE", "false")
    inputs = iter(["exit"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(inputs))

    rc = cli.main([])
    assert rc == 0
    assert mock_anthropic.messages.create.call_count == 0
    out = capsys.readouterr().out
    assert "modo interactivo" in out
    assert "Hasta pronto" in out


def test_cli_repl_runs_one_turn_then_exits(
    mock_anthropic: MagicMock,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """REPL ejecuta un turno y luego sale con 'salir'."""
    monkeypatch.setenv("SEGURITO_ENABLED_ORGANISMOS", '["cmf"]')
    monkeypatch.setenv("SEGURITO_ENABLE_TRIAGE", "false")
    inputs = iter(["hola", "salir"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(inputs))

    rc = cli.main([])
    assert rc == 0
    assert mock_anthropic.messages.create.call_count >= 1
    out = capsys.readouterr().out
    assert "Cascada" in out
    assert "respuesta" in out
    assert "turnos=1" in out


def test_cli_repl_eof_exits_cleanly(
    mock_anthropic: MagicMock,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """EOF (Ctrl+Z+Enter / Ctrl+D) sale sin error."""
    monkeypatch.setenv("SEGURITO_ENABLED_ORGANISMOS", '["cmf"]')
    monkeypatch.setenv("SEGURITO_ENABLE_TRIAGE", "false")

    def _raise_eof(_prompt: str = "") -> str:
        raise EOFError

    monkeypatch.setattr("builtins.input", _raise_eof)
    rc = cli.main([])
    assert rc == 0
    assert "Hasta pronto" in capsys.readouterr().out


def test_cli_repl_reset_clears_conversation(
    mock_anthropic: MagicMock,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """':reset' continúa sin matar el REPL."""
    monkeypatch.setenv("SEGURITO_ENABLED_ORGANISMOS", '["cmf"]')
    monkeypatch.setenv("SEGURITO_ENABLE_TRIAGE", "false")
    inputs = iter([":reset", "exit"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(inputs))

    rc = cli.main([])
    assert rc == 0
    assert "(nueva conversación)" in capsys.readouterr().out
