"""Shared HTTP client with simple retry on 429/5xx."""

from __future__ import annotations

import time
from typing import Any

import httpx

from .config import get_settings

RETRY_STATUS = (429, 500, 502, 503, 504)

_client: httpx.Client | None = None


def client() -> httpx.Client:
    global _client
    if _client is None:
        _client = httpx.Client(
            headers={"User-Agent": get_settings().user_agent},
            timeout=httpx.Timeout(60.0, connect=10.0),
            follow_redirects=True,
        )
    return _client


def set_client(c: httpx.Client | None) -> None:
    """Swap the client (a dry run injects an httpx.MockTransport)."""
    global _client
    _client = c


def request_json(method: str, url: str, retries: int = 3, **kwargs: Any) -> Any:
    for attempt in range(retries + 1):
        response = client().request(method, url, **kwargs)
        if response.status_code in RETRY_STATUS and attempt < retries:
            wait = float(response.headers.get("retry-after", 2 ** (attempt + 1)))
            time.sleep(min(wait, 30))
            continue
        response.raise_for_status()
        return response.json()
    raise RuntimeError("unreachable")
