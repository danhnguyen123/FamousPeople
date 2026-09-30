"""Supported narration languages and per-language defaults."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Language:
    code: str  # ISO 639-1, also used as the Google "hl" parameter
    name: str
    words_per_minute: int  # used to estimate durations when TTS is skipped


LANGUAGES: dict[str, Language] = {
    "en": Language("en", "English", 150),
    "fr": Language("fr", "French", 155),
    "de": Language("de", "German", 130),
    "it": Language("it", "Italian", 150),
    "pl": Language("pl", "Polish", 125),
    "nl": Language("nl", "Dutch", 140),
}


def get_language(code: str) -> Language:
    try:
        return LANGUAGES[code.lower()]
    except KeyError:
        supported = ", ".join(LANGUAGES)
        raise ValueError(f"Unsupported language '{code}'. Supported: {supported}") from None
