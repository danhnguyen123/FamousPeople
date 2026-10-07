"""Vietnamese translations for the review page, through the Gemini API.

Only `docugen review` uses this: it helps a Vietnamese editor read the narration
and the groups. The pipeline itself never depends on it. Translations are cached
in projects/<slug>/translations.json, so each text is sent once.

Everything not cached yet goes in one request, so Gemini sees the whole script and
keeps names consistent. Each text carries its number, so a skipped line costs only
that line: whatever is still missing afterwards is sent again in chunks of CHUNK.
"""

from __future__ import annotations

import json
import logging
import threading
import time

from .config import Settings
from .http import request_json
from .llm import prompt
from .project import Project

log = logging.getLogger(__name__)

API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
CACHE = "translations.json"
CHUNK = 80  # strings per request for what the single request left out
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
                log.info("translate: %d texts in one request with %s", len(missing), self.settings.translate_model)
                try:
                    cache.update(self._request(missing))
                    self._save(cache)
                except Exception as exc:  # an error or a cut answer: the chunks below redo it
                    log.warning("translate: single request failed: %s", exc)
                # Whatever is still missing (a skipped line, a failed request) goes again in chunks.
                rest = [t for t in missing if t not in cache]
                for i in range(0, len(rest), CHUNK):
                    chunk = rest[i : i + CHUNK]
                    try:
                        cache.update(self._request(chunk))
                    except Exception as exc:  # keep what is done, the next call retries the rest
                        log.warning("translate: %d texts failed: %s", len(chunk), exc)
                        break
                    self._save(cache)
            return {t: cache[t] for t in texts if t in cache}

    def _save(self, cache: dict[str, str]) -> None:
        self.project.path(CACHE).write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")

    def _request(self, texts: list[str]) -> dict[str, str]:
        """Translations of the texts Gemini answered for; each text carries its number."""
        items = [{"i": n, "text": t} for n, t in enumerate(texts)]
        started = time.monotonic()
        data = request_json(
            "POST",
            API.format(model=self.settings.translate_model),
            headers={"x-goog-api-key": self.settings.gemini_api_key},
            json={
                "systemInstruction": {"parts": [{"text": prompt("translator")}]},
                "contents": [{"role": "user", "parts": [{"text": json.dumps(items, ensure_ascii=False)}]}],
                "generationConfig": {
                    "temperature": 0.2,
                    "responseMimeType": "application/json",
                    "responseSchema": {
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "properties": {"i": {"type": "INTEGER"}, "vi": {"type": "STRING"}},
                            "required": ["i", "vi"],
                        },
                    },
                },
            },
            timeout=600,  # the whole script in one answer can take a few minutes
        )
        usage = data.get("usageMetadata") or {}
        log.info("translate: %d texts, %s input tokens, %s output tokens, %.0f s, finish %s", len(texts),
                 usage.get("promptTokenCount"), usage.get("candidatesTokenCount"), time.monotonic() - started,
                 (data.get("candidates") or [{}])[0].get("finishReason"))
        parts = data["candidates"][0]["content"]["parts"]
        out = json.loads("".join(part.get("text", "") for part in parts))
        done = {texts[x["i"]]: str(x["vi"]).strip() for x in out
                if isinstance(x, dict) and isinstance(x.get("i"), int) and 0 <= x["i"] < len(texts) and x.get("vi")}
        if len(done) < len(texts):
            log.warning("translate: %d of %d texts came back without a translation", len(texts) - len(done), len(texts))
        return done
