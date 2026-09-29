"""Openverse: a search index over openly licensed images (Flickr, museums, ...)."""

from __future__ import annotations

from ..http import get_json
from ..models import Candidate
from .base import domain_of

API = "https://api.openverse.org/v1/images/"


class Openverse:
    name = "openverse"

    def search(self, query: str, limit: int = 20) -> list[Candidate]:
        data = get_json(API, {"q": query, "page_size": str(limit), "mature": "false"})
        out = []
        for r in data.get("results", []):
            code = (r.get("license") or "").lower()
            version = r.get("license_version") or ""
            label = code.upper() if code in ("pdm", "cc0") else f"CC {code.upper()} {version}".strip()
            out.append(
                Candidate(
                    provider="openverse",
                    image_url=r["url"],
                    thumb_url=r.get("thumbnail"),
                    page_url=r.get("foreign_landing_url"),
                    title=r.get("title") or "",
                    tags=[t.get("name", "") for t in r.get("tags") or []],
                    author=r.get("creator"),
                    license=label,
                    license_url=r.get("license_url"),
                    width=r.get("width"),
                    height=r.get("height"),
                    query=query,
                    source_domain=domain_of(r.get("foreign_landing_url")) or r.get("source"),
                )
            )
        return out
