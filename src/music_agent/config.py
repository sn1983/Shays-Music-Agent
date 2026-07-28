"""Application configuration, loaded from environment variables / .env."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]

_TRUTHY = {"1", "true", "yes", "on"}


class ConfigError(RuntimeError):
    """Raised when a required setting is missing or malformed."""


@dataclass(frozen=True)
class Settings:
    """Immutable runtime configuration for the agent."""

    claude_api_key: str
    claude_model: str
    claude_effort: str
    telegram_bot_token: str
    telegram_chat_id: str
    telegram_parse_mode: str
    facebook_enabled: bool
    facebook_page_id: str
    facebook_access_token: str
    facebook_api_version: str
    database_path: Path
    timezone: str
    log_level: str
    post_time: str
    songs_per_day: int
    dry_run: bool

    @property
    def post_hour(self) -> int:
        return int(self.post_time.split(":")[0])

    @property
    def post_minute(self) -> int:
        return int(self.post_time.split(":")[1])


def _require(name: str, *, allow_missing: bool) -> str:
    value = os.getenv(name, "").strip()
    if not value and not allow_missing:
        raise ConfigError(
            f"Missing required environment variable {name!r}. "
            "Copy .env.example to .env and fill it in (see docs/TELEGRAM_SETUP.md)."
        )
    return value


def _resolve(path_value: str) -> Path:
    path = Path(path_value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def load_settings(*, require_secrets: bool = True) -> Settings:
    """Read settings from the environment, loading .env first if present."""
    load_dotenv(PROJECT_ROOT / ".env")

    parse_mode = os.getenv("TELEGRAM_PARSE_MODE", "HTML").strip() or "HTML"
    if parse_mode not in {"HTML", "MarkdownV2"}:
        raise ConfigError("TELEGRAM_PARSE_MODE must be either 'HTML' or 'MarkdownV2'.")

    post_time = os.getenv("POST_TIME", "20:00").strip() or "20:00"
    try:
        hour, minute = (int(part) for part in post_time.split(":"))
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError
    except ValueError as exc:
        raise ConfigError("POST_TIME must look like 'HH:MM', e.g. '20:00'.") from exc

    facebook_enabled = os.getenv("FACEBOOK_ENABLED", "false").strip().lower() in _TRUTHY
    facebook_page_id = os.getenv("FACEBOOK_PAGE_ID", "").strip()
    facebook_access_token = os.getenv("FACEBOOK_ACCESS_TOKEN", "").strip()
    if facebook_enabled and require_secrets and not (facebook_page_id and facebook_access_token):
        raise ConfigError(
            "FACEBOOK_ENABLED is on but FACEBOOK_PAGE_ID / FACEBOOK_ACCESS_TOKEN are missing. "
            "See docs/FACEBOOK_SETUP.md, or set FACEBOOK_ENABLED=false."
        )

    settings = Settings(
        claude_api_key=_require("CLAUDE_API_KEY", allow_missing=not require_secrets),
        claude_model=os.getenv("CLAUDE_MODEL", "claude-opus-5").strip() or "claude-opus-5",
        claude_effort=os.getenv("CLAUDE_EFFORT", "high").strip() or "high",
        telegram_bot_token=_require("TELEGRAM_BOT_TOKEN", allow_missing=not require_secrets),
        telegram_chat_id=_require("TELEGRAM_CHAT_ID", allow_missing=not require_secrets),
        telegram_parse_mode=parse_mode,
        facebook_enabled=facebook_enabled,
        facebook_page_id=facebook_page_id,
        facebook_access_token=facebook_access_token,
        facebook_api_version=os.getenv("FACEBOOK_API_VERSION", "v21.0").strip() or "v21.0",
        database_path=_resolve(os.getenv("DATABASE_PATH", "storage/music_agent.db")),
        timezone=os.getenv("TIMEZONE", "Asia/Jerusalem").strip() or "Asia/Jerusalem",
        log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO",
        post_time=post_time,
        songs_per_day=max(1, int(os.getenv("SONGS_PER_DAY", "1") or 1)),
        dry_run=os.getenv("DRY_RUN", "false").strip().lower() in _TRUTHY,
    )
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    return settings
