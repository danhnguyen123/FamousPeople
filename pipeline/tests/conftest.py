from __future__ import annotations

import io

import httpx
import pytest
from PIL import Image

from docugen import http
from docugen.config import Settings
from docugen.models import Candidate, EntityInfo, VisualBrief


@pytest.fixture
def settings(tmp_path) -> Settings:
    s = Settings()
    s.license_policy = "strict"
    s.blocked_domains = []
    s.preferred_domains = []
    s.enable_clip = False
    s.projects_dir = tmp_path / "projects"
    s.remotion_dir = tmp_path / "video"
    return s


@pytest.fixture
def ryder() -> EntityInfo:
    return EntityInfo(
        name="Winona Ryder",
        qid="Q106997",
        labels={"en": "Winona Ryder", "pl": "Winona Ryder"},
        aliases=["Winona Laura Horowitz"],
        birth_year=1971,
        commons_category="Winona Ryder",
    )


def brief(**kw) -> VisualBrief:
    base = dict(
        scene_index=0,
        visual_type="person_event",
        primary_entity="Winona Ryder",
        other_entities=[],
        year_from=1994,
        year_to=1994,
        event_anchor="Little Women premiere",
        location="Los Angeles",
        specific_queries=["Winona Ryder Little Women premiere 1994"],
        broad_queries=["Winona Ryder 1990s"],
        native_queries=[],
        clip_prompt="A young actress smiling at a 1990s film premiere",
    )
    base.update(kw)
    return VisualBrief(**base)


def cand(**kw) -> Candidate:
    base = dict(
        provider="wikimedia",
        image_url="https://upload.wikimedia.org/a.jpg",
        title="Winona Ryder at the Little Women premiere, 1994",
        license="CC BY-SA 3.0",
        width=2000,
        height=1400,
        source_domain="commons.wikimedia.org",
    )
    base.update(kw)
    return Candidate(**base)


def jpeg_bytes(color=(120, 80, 40), size=(1600, 1000), pattern: int = 0) -> bytes:
    import random

    # Blocky noise seeded by `pattern`: equal patterns give equal perceptual hashes.
    rng = random.Random(pattern)
    small = Image.new("RGB", (16, 10))
    small.putdata([tuple(min(255, c + rng.randint(0, 120)) for c in color) for _ in range(160)])
    img = small.resize(size, Image.NEAREST)
    buf = io.BytesIO()
    img.save(buf, "JPEG")
    return buf.getvalue()


@pytest.fixture
def mock_http():
    """Install an httpx.MockTransport; tests register url-substring -> response."""
    routes: dict[str, httpx.Response | callable] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        for key, value in routes.items():
            if key in url:
                return value(request) if callable(value) else value
        return httpx.Response(404, json={})

    http.set_client(httpx.Client(transport=httpx.MockTransport(handler)))
    yield routes
    http.set_client(None)
