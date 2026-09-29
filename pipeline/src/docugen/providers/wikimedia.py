"""Wikimedia Commons: the best free source for identified, dated celebrity photos.

Every file has a license, an author and human-written categories such as
"Winona Ryder in 1994" or "66th Academy Awards", which is exactly the
metadata the entity-first scorer needs.
"""

from __future__ import annotations

from typing import Any

from ..http import get_json
from ..models import Candidate
from .base import domain_of, strip_html

API = "https://commons.wikimedia.org/w/api.php"
THUMB_WIDTH = 2400

_BASE_PARAMS = {
    "action": "query",
    "format": "json",
    "prop": "imageinfo",
    "iiprop": "url|size|extmetadata|mime",
    "iiurlwidth": str(THUMB_WIDTH),
    "iiextmetadatafilter": "ObjectName|ImageDescription|DateTimeOriginal|DateTime|"
    "LicenseShortName|LicenseUrl|Artist|Credit|Categories|UsageTerms|Copyrighted",
}


def _meta(ext: dict, key: str) -> str:
    return strip_html(ext.get(key, {}).get("value"))


def _to_candidate(page: dict[str, Any], query: str) -> Candidate | None:
    infos = page.get("imageinfo") or []
    if not infos:
        return None
    info = infos[0]
    if not str(info.get("mime", "")).startswith("image/") or info.get("mime") == "image/svg+xml":
        return None
    ext = info.get("extmetadata", {})
    title = page.get("title", "").removeprefix("File:")
    categories = [c for c in _meta(ext, "Categories").split("|") if c]
    return Candidate(
        provider="wikimedia",
        image_url=info.get("thumburl") or info["url"],
        thumb_url=info.get("thumburl"),
        page_url=info.get("descriptionurl"),
        title=_meta(ext, "ObjectName") or title,
        description=_meta(ext, "ImageDescription"),
        categories=categories,
        author=_meta(ext, "Artist") or _meta(ext, "Credit") or None,
        license=_meta(ext, "LicenseShortName") or None,
        license_url=_meta(ext, "LicenseUrl") or None,
        width=info.get("width"),
        height=info.get("height"),
        date=_meta(ext, "DateTimeOriginal") or None,
        query=query,
        source_domain=domain_of(info.get("descriptionurl")) or "commons.wikimedia.org",
    )


def _pages(data: dict, query: str) -> list[Candidate]:
    pages = sorted(data.get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 0))
    return [c for c in (_to_candidate(p, query) for p in pages) if c]


class WikimediaCommons:
    name = "wikimedia"

    def search(self, query: str, limit: int = 20) -> list[Candidate]:
        data = get_json(
            API,
            {
                **_BASE_PARAMS,
                "generator": "search",
                "gsrsearch": f"{query} filetype:bitmap",
                "gsrnamespace": "6",
                "gsrlimit": str(limit),
            },
        )
        return _pages(data, query)

    def category(self, category: str, limit: int = 50) -> list[Candidate]:
        """Files in a category, e.g. 'Winona Ryder in 1994' (no 'Category:' prefix)."""
        data = get_json(
            API,
            {
                **_BASE_PARAMS,
                "generator": "categorymembers",
                "gcmtitle": f"Category:{category}",
                "gcmtype": "file",
                "gcmlimit": str(limit),
            },
        )
        return _pages(data, f"Category:{category}")
