"""Supported narration languages and the search parameters that go with each."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Language:
    code: str  # ISO 639-1: DataForSEO language_code, Brave search_lang
    name: str
    dataforseo_location: int  # Google geotarget code of the main country
    bing_market: str  # SearchAPI Bing market_code


LANGUAGES: dict[str, Language] = {
    "en": Language("en", "English", 2840, "en-US"),
    "fr": Language("fr", "French", 2250, "fr-FR"),
    "de": Language("de", "German", 2276, "de-DE"),
    "it": Language("it", "Italian", 2380, "it-IT"),
    "pl": Language("pl", "Polish", 2616, "pl-PL"),
    "nl": Language("nl", "Dutch", 2528, "nl-NL"),
}


def get_language(code: str) -> Language:
    try:
        return LANGUAGES[code.lower()]
    except KeyError:
        supported = ", ".join(LANGUAGES)
        raise ValueError(f"Unsupported language '{code}'. Supported: {supported}") from None
