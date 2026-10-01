"""Runtime settings, read from environment variables (and a .env file)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[3]

load_dotenv(REPO_ROOT / ".env")

SOURCES = ("dataforseo", "bing", "brave")


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    return value if value else default


def _env_list(name: str, default: str = "") -> list[str]:
    raw = _env(name, default) or ""
    return [item.strip().lower() for item in raw.split(",") if item.strip()]


def _env_int(name: str, default: int) -> int:
    return int(_env(name, str(default)) or default)


@dataclass
class Settings:
    # Claude: plan (SRT to scenes, groups, keywords) and select (validate search results)
    anthropic_api_key: str | None = field(
        default_factory=lambda: _env("DOCUGEN_ANTHROPIC_API_KEY", _env("ANTHROPIC_API_KEY"))
    )
    model: str = field(default_factory=lambda: _env("DOCUGEN_MODEL", "claude-opus-5-5"))
    select_model: str = field(
        default_factory=lambda: _env("DOCUGEN_SELECT_MODEL", _env("DOCUGEN_MODEL", "claude-opus-5-5"))
    )
    select_batch: bool = field(default_factory=lambda: _env("DOCUGEN_SELECT_BATCH", "0") == "1")

    # Image search: every listed source is queried for each group
    sources: list[str] = field(default_factory=lambda: _env_list("DOCUGEN_SEARCH", ",".join(SOURCES)))
    candidates_per_source: int = field(
        default_factory=lambda: _env_int("DOCUGEN_CANDIDATES_PER_SOURCE", 40)
    )
    dataforseo_login: str | None = field(default_factory=lambda: _env("DATAFORSEO_LOGIN"))
    dataforseo_password: str | None = field(default_factory=lambda: _env("DATAFORSEO_PASSWORD"))
    dataforseo_live: bool = field(default_factory=lambda: _env("DOCUGEN_DATAFORSEO_LIVE", "0") == "1")
    dataforseo_location: int | None = field(
        default_factory=lambda: int(v) if (v := _env("DATAFORSEO_LOCATION_CODE")) else None
    )
    searchapi_api_key: str | None = field(default_factory=lambda: _env("SEARCHAPI_API_KEY"))
    brave_api_key: str | None = field(default_factory=lambda: _env("BRAVE_API_KEY"))
    brave_safesearch: str = field(default_factory=lambda: _env("DOCUGEN_BRAVE_SAFESEARCH", "strict"))
    brave_country: str | None = field(default_factory=lambda: _env("DOCUGEN_BRAVE_COUNTRY"))
    # Seconds between Brave calls: the free plan allows 1 request per second
    brave_interval: float = field(default_factory=lambda: float(_env("DOCUGEN_BRAVE_INTERVAL", "1.1") or 1.1))
    blocked_domains: list[str] = field(default_factory=lambda: _env_list("DOCUGEN_BLOCKED_DOMAINS"))

    # Images
    min_pool: int = field(default_factory=lambda: _env_int("DOCUGEN_MIN_POOL", 3))
    min_side: int = field(default_factory=lambda: _env_int("DOCUGEN_MIN_SIDE", 600))
    reuse_gap: float = field(default_factory=lambda: float(_env("DOCUGEN_REUSE_GAP", "30") or 30))
    user_agent: str = field(
        default_factory=lambda: _env(
            "DOCUGEN_USER_AGENT",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0 Safari/537.36",
        )
    )

    projects_dir: Path = field(default_factory=lambda: REPO_ROOT / "projects")
    remotion_dir: Path = field(default_factory=lambda: REPO_ROOT / "video")


def get_settings() -> Settings:
    return Settings()
