"""Shared HTTP client with polite defaults and simple retry on 429/5xx."""

from __future__ import annotations

import time
from typing import Any

import httpx

from .config import get_settings

_client: httpx.Client | None = None


def client() -> httpx.Client:
    global _client
    if _client is None:
        _client = httpx.Client(
            headers={"User-Agent": get_settings().user_agent},
            timeout=httpx.Timeout(30.0, connect=10.0),
            follow_redirects=True,
        )
    return _client


def set_client(c: httpx.Client | None) -> None:
    """Swap the client (tests inject an httpx.MockTransport)."""
    global _client
    _client = c


def get_json(url: str, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None,
             retries: int = 3) -> Any:
    for attempt in range(retries + 1):
        response = client().get(url, params=params, headers=headers)
        if response.status_code in (429, 500, 502, 503, 504) and attempt < retries:
            wait = float(response.headers.get("retry-after", 2 ** (attempt + 1)))
            time.sleep(min(wait, 30))
            continue
        response.raise_for_status()
        return response.json()
    raise RuntimeError("unreachable")
