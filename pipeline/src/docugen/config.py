"""Runtime settings, read from environment variables (and a .env file)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[3]

load_dotenv(REPO_ROOT / ".env")


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    return value if value else default


def _env_list(name: str) -> list[str]:
    raw = _env(name, "") or ""
    return [item.strip().lower() for item in raw.split(",") if item.strip()]


@dataclass
class Settings:
    anthropic_model: str = field(default_factory=lambda: _env("DOCUGEN_MODEL", "claude-opus-5-5"))
    pexels_api_key: str | None = field(default_factory=lambda: _env("PEXELS_API_KEY"))
    brave_api_key: str | None = field(default_factory=lambda: _env("BRAVE_API_KEY"))
    elevenlabs_api_key: str | None = field(default_factory=lambda: _env("ELEVENLABS_API_KEY"))
    elevenlabs_model: str = field(
        default_factory=lambda: _env("ELEVENLABS_MODEL", "eleven_multilingual_v2")
    )
    # Wikimedia asks every API client to send a descriptive User-Agent with contact info.
    user_agent: str = field(
        default_factory=lambda: _env(
            "DOCUGEN_USER_AGENT", "docugen/0.1 (documentary research tool; contact: set DOCUGEN_USER_AGENT)"
        )
    )
    blocked_domains: list[str] = field(default_factory=lambda: _env_list("DOCUGEN_BLOCKED_DOMAINS"))
    preferred_domains: list[str] = field(
        default_factory=lambda: _env_list("DOCUGEN_PREFERRED_DOMAINS")
    )
    enable_clip: bool = field(default_factory=lambda: _env("DOCUGEN_CLIP", "auto") != "off")
    projects_dir: Path = field(default_factory=lambda: REPO_ROOT / "projects")
    remotion_dir: Path = field(default_factory=lambda: REPO_ROOT / "video")

    def elevenlabs_voice(self, language: str) -> str | None:
        """Voice per language (ELEVENLABS_VOICE_DE, ...), falling back to ELEVENLABS_VOICE_ID."""
        return _env(f"ELEVENLABS_VOICE_{language.upper()}", _env("ELEVENLABS_VOICE_ID"))


def get_settings() -> Settings:
    return Settings()
