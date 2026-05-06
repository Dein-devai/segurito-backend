"""Configuración tipada de la aplicación.

Un único objeto `Settings` que carga desde variables de entorno y `.env`.
Todo el resto del código consume este objeto vía dependency injection.
Reemplaza el uso disperso de `os.getenv` en módulos.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Configuración global. Las variables se leen del entorno o de `.env`."""

    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Anthropic / LLM ----------------------------------------------------
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    # ``model_chat`` se conserva por retrocompatibilidad (F4-F5). El
    # ``ChatService`` usa la cascada Haiku → Sonnet → Opus declarada abajo.
    model_chat: str = Field(default="claude-sonnet-4-5", alias="SEGURITO_MODEL_CHAT")
    max_tool_iterations: int = Field(default=5, alias="SEGURITO_MAX_TOOL_ITERATIONS")
    tool_loop_timeout_s: float = Field(default=30.0, alias="SEGURITO_TOOL_LOOP_TIMEOUT")
    max_user_input_chars: int = Field(default=2000, alias="SEGURITO_MAX_USER_INPUT")

    # --- Multi-modelo (cascada Haiku → Sonnet → Opus) ----------------------
    model_triage: str = Field(
        default="claude-haiku-4-5", alias="SEGURITO_MODEL_TRIAGE"
    )
    model_default: str = Field(
        default="claude-sonnet-4-5", alias="SEGURITO_MODEL_DEFAULT"
    )
    model_escalation: str = Field(
        default="claude-opus-4-6", alias="SEGURITO_MODEL_ESCALATION"
    )
    thinking_budget_tokens: int = Field(
        default=2048, alias="SEGURITO_THINKING_BUDGET"
    )
    escalation_keywords: tuple[str, ...] = Field(
        default=(
            "demanda",
            "tribunal",
            "fraude grande",
            "estafa millonaria",
            "insider",
            "información privilegiada",
            "acción legal",
            "querella",
        ),
        alias="SEGURITO_ESCALATION_KEYWORDS",
    )
    allow_model_override: bool = Field(
        default=False, alias="SEGURITO_ALLOW_MODEL_OVERRIDE"
    )
    enable_prompt_cache: bool = Field(
        default=True, alias="SEGURITO_ENABLE_PROMPT_CACHE"
    )
    enable_triage: bool = Field(
        default=True, alias="SEGURITO_ENABLE_TRIAGE"
    )

    # --- Rate limits transversales (5 niveles) -----------------------------
    rate_limit_per_ip_per_min: int = Field(
        default=60, alias="SEGURITO_RL_IP_MIN"
    )
    rate_limit_per_ip_per_day: int = Field(
        default=1000, alias="SEGURITO_RL_IP_DAY"
    )
    rate_limit_per_conversation_turns: int = Field(
        default=30, alias="SEGURITO_RL_CONV_TURNS"
    )
    rate_limit_per_conversation_per_hour: int = Field(
        default=120, alias="SEGURITO_RL_CONV_HOUR"
    )
    rate_limit_sonnet_per_min: int = Field(
        default=40, alias="SEGURITO_RL_SONNET_MIN"
    )
    rate_limit_opus_per_min_global: int = Field(
        default=10, alias="SEGURITO_RL_OPUS_MIN_GLOBAL"
    )
    rate_limit_opus_per_conversation: int = Field(
        default=5, alias="SEGURITO_RL_OPUS_CONV"
    )
    cost_budget_usd_per_day: float = Field(
        default=10.0, alias="SEGURITO_COST_BUDGET_DAY_USD"
    )

    # --- Storage ------------------------------------------------------------
    data_dir: Path = Field(default=ROOT_DIR / "data", alias="SEGURITO_DATA_DIR")
    chroma_db_path: Path = Field(default=ROOT_DIR / "chroma_db", alias="SEGURITO_CHROMA_PATH")
    log_path: Path = Field(default=ROOT_DIR / "interaction_log.jsonl", alias="SEGURITO_LOG_PATH")
    db_path: Path = Field(default=ROOT_DIR / "segurito.db", alias="SEGURITO_DB_PATH")

    # --- Embedding ----------------------------------------------------------
    embed_model_name: str = Field(
        default="paraphrase-multilingual-MiniLM-L12-v2",
        alias="SEGURITO_EMBED_MODEL",
    )

    # --- Plugins ------------------------------------------------------------
    enabled_organismos: tuple[str, ...] = Field(
        default=("cmf", "legal", "sernac", "sii"),
        alias="SEGURITO_ENABLED_ORGANISMOS",
    )

    # --- API ----------------------------------------------------------------
    cors_origins: tuple[str, ...] = Field(default=("*",), alias="SEGURITO_CORS_ORIGINS")
    log_level: str = Field(default="INFO", alias="SEGURITO_LOG_LEVEL")

    # --- MCP server ---------------------------------------------------------
    mcp_host: str = Field(default="127.0.0.1", alias="SEGURITO_MCP_HOST")
    mcp_port: int = Field(default=8765, alias="SEGURITO_MCP_PORT")

    # --- Conversación -------------------------------------------------------
    conversation_ttl_seconds: int = Field(
        default=1800, alias="SEGURITO_CONVERSATION_TTL"
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Singleton para inyección de dependencias.

    Tests pueden sobrescribir invocando `get_settings.cache_clear()` y luego
    setear variables de entorno, o usando `dependency_overrides` de FastAPI.
    """
    return Settings()
