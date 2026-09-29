from __future__ import annotations

import html
import re
from typing import Protocol
from urllib.parse import urlparse

from ..models import Candidate


class Provider(Protocol):
    name: str

    def search(self, query: str, limit: int = 20) -> list[Candidate]: ...


_TAG = re.compile(r"<[^>]+>")


def strip_html(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(html.unescape(_TAG.sub(" ", value)).split())


def domain_of(url: str | None) -> str | None:
    if not url:
        return None
    host = urlparse(url).hostname or ""
    return host.removeprefix("www.") or None
