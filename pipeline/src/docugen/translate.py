"""Vietnamese translations for the review page, through the Gemini API.

Only `docugen review` uses this: it helps a Vietnamese editor read the narration
and the groups. The pipeline itself never depends on it. Translations are cached
in projects/<slug>/translations.json, so each text is sent once.
"""

from __future__ import annotations

import json
import logging
import threading

from .config import Settings
from .http import request_json
from .llm import prompt
from .project import Project

log = logging.getLogger(__name__)

API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
CACHE = "translations.json"
CHUNK = 80  # strings per request
_lock = threading.Lock()  # one translation run at a time per process


class Translator:
    def __init__(self, project: Project, settings: Settings):
        self.project = project
        self.settings = settings

    @property
    def unavailable(self) -> str | None:
        """Why translation is off, or None when it can run."""
        if not self.settings.gemini_api_key:
            return "GEMINI_API_KEY chưa được đặt"
        if self.project.language == "vi":
            return "kịch bản đã là tiếng Việt"
        return None

    def _cache(self) -> dict[str, str]:
        path = self.project.path(CACHE)
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    def translate(self, texts: list[str]) -> dict[str, str]:
        """{text: Vietnamese} for every text, calling Gemini only for the ones not cached yet."""
        with _lock:
            cache = self._cache()
            missing = [t for t in dict.fromkeys(texts) if t and t not in cache]
            if missing and not self.unavailable:
                log.info("translate: %d texts with %s", len(missing), self.settings.translate_model)
                for i in range(0, len(missing), CHUNK):
                    chunk = missing[i : i + CHUNK]
                    try:
                        cache.update(zip(chunk, self._request(chunk)))
                    except Exception as exc:  # keep what is done, the next call retries the rest
                        log.warning("translate: %d texts failed: %s", len(chunk), exc)
                        break
                    self.project.path(CACHE).write_text(
                        json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
            return {t: cache[t] for t in texts if t in cache}

    def _request(self, texts: list[str]) -> list[str]:
        data = request_json(
            "POST",
            API.format(model=self.settings.translate_model),
            headers={"x-goog-api-key": self.settings.gemini_api_key},
            json={
                "systemInstruction": {"parts": [{"text": prompt("translator")}]},
                "contents": [{"role": "user", "parts": [{"text": json.dumps(texts, ensure_ascii=False)}]}],
                "generationConfig": {
                    "temperature": 0.2,
                    "responseMimeType": "application/json",
                    "responseSchema": {"type": "ARRAY", "items": {"type": "STRING"}},
                },
            },
            timeout=120,
        )
        parts = data["candidates"][0]["content"]["parts"]
        out = json.loads("".join(p.get("text", "") for p in parts))
        if not isinstance(out, list) or len(out) != len(texts):
            raise ValueError(f"expected {len(texts)} translations, got {len(out) if isinstance(out, list) else 'none'}")
        return [str(x).strip() for x in out]
