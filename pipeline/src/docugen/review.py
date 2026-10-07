"""docugen review: a local web page to check the image of every scene.

It reads plan.csv (written by the download stage) and shows, per scene, the cues,
the narration, the group's keywords and the image, with a Vietnamese translation
of the narration and the group when GEMINI_API_KEY is set (translate.py).

Pasting an image link into a row downloads it to manual/scene_007.jpg, records
the link in manual/links.json, and updates images.json and plan.csv right away.
timeline.json is removed because it no longer matches, so the next
`docugen run` rebuilds it with the new images.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import mimetypes
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from PIL import Image

from .config import get_settings
from .download import IMAGE_EXTS, MAX_LONG_SIDE, write_reports
from .http import client
from .models import GroupSearch, GroupSelection, Plan, SceneImage
from .pipeline import stage_download
from .project import Project
from .translate import Translator

log = logging.getLogger(__name__)

PAGE = Path(__file__).parent / "review.html"
LINKS = "manual/links.json"
SERVED_DIRS = ("assets", "manual")
MAX_BYTES = 30 * 1024 * 1024
_write_lock = threading.Lock()  # one change to images.json / plan.csv at a time


def _links(p: Project) -> dict[str, str]:
    path = p.path(LINKS)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _save_links(p: Project, links: dict[str, str]) -> None:
    path = p.path(LINKS)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(links, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")


def scenes(p: Project) -> list[dict]:
    """plan.csv rows, plus the manual link of each scene."""
    links = _links(p)
    with p.path("plan.csv").open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    return [
        {
            "scene": int(r["Scene"]),
            "start": float(r["Start"] or 0),
            "cues": r["Cues"],
            "text": r["Text"],
            "group": r["Group"],
            "subject": r["Subject"],
            "context": r["Context"],
            "keywords": [k.strip() for k in r["Keywords"].split("|") if k.strip()],
            "image": r["Image file"] if not r["Image file"].startswith("(") else None,
            "source": r["Source"],
            "reused": r["Reused"] == "yes",
            "note": r["Note"],
            "page_url": r["Page URL"],
            "manual_url": links.get(r["Scene"]),
        }
        for r in rows
    ]


def _remove_manual_files(p: Project, scene: int) -> None:
    folder = p.path("manual")
    if folder.exists():
        for path in folder.glob(f"scene_{scene:03d}.*"):
            if path.suffix.lower() in IMAGE_EXTS:
                path.unlink()


def _fetch_image(url: str) -> Image.Image:
    # Messages are shown as is on the (Vietnamese) review page.
    if urlparse(url).scheme not in ("http", "https"):
        raise ValueError("link phải bắt đầu bằng http:// hoặc https://")
    try:
        response = client().get(url, timeout=30)
    except Exception as exc:
        raise ValueError(f"không kết nối được tới link ({type(exc).__name__})") from None
    if response.status_code >= 400:
        raise ValueError(f"không tải được ảnh (HTTP {response.status_code})")
    if len(response.content) > MAX_BYTES:
        raise ValueError("file lớn hơn 30 MB")
    try:
        return Image.open(io.BytesIO(response.content)).convert("RGB")
    except Exception:
        raise ValueError("link này không phải là ảnh (hãy dùng link trực tiếp tới file ảnh)") from None


def _rewrite_outputs(p: Project, images: list[SceneImage]) -> None:
    p.save("images.json", images)
    write_reports(p, p.load("plan.json", Plan), p.cues(), {s.group: s for s in p.load("search.json", list[GroupSearch])},
                  {s.group: s for s in p.load("select.json", list[GroupSelection])}, images)
    p.path("timeline.json").unlink(missing_ok=True)


def set_manual(p: Project, scene: int, url: str) -> None:
    images = p.load("images.json", list[SceneImage])
    if not 1 <= scene <= len(images):
        raise ValueError(f"cảnh {scene} không tồn tại")
    image = _fetch_image(url)
    image.thumbnail((MAX_LONG_SIDE, MAX_LONG_SIDE))
    _remove_manual_files(p, scene)
    target = p.path(f"manual/scene_{scene:03d}.jpg")
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target, "JPEG", quality=90)
    links = _links(p)
    links[str(scene)] = url
    _save_links(p, links)
    old = images[scene - 1]
    images[scene - 1] = SceneImage(scene=scene, group=old.group, file=str(target.relative_to(p.root)),
                                   page_url=url, manual=True)
    _rewrite_outputs(p, images)


def clear_manual(p: Project, scene: int) -> None:
    _remove_manual_files(p, scene)
    links = _links(p)
    links.pop(str(scene), None)
    _save_links(p, links)
    # Rebuilding the whole stage gives the scene back its pool image; other scenes keep theirs.
    stage_download(p, get_settings())
    p.path("timeline.json").unlink(missing_ok=True)


def translations(p: Project, translator: Translator | None) -> dict:
    """Vietnamese for every narration line, subject and context shown on the page."""
    if translator is None:
        return {"available": False, "reason": "đã tắt dịch (--no-translate)", "texts": {}}
    if translator.unavailable:
        return {"available": False, "reason": translator.unavailable, "texts": {}}
    rows = scenes(p)
    texts = [t for s in rows for t in (s["text"], s["subject"], s["context"])]
    return {"available": True, "texts": translator.translate(texts)}


def make_handler(p: Project, translator: Translator | None) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args) -> None:
            log.debug(fmt, *args)

        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, data, status: int = 200) -> None:
            self._send(status, json.dumps(data, ensure_ascii=False).encode(), "application/json; charset=utf-8")

        def do_GET(self) -> None:
            path = unquote(urlparse(self.path).path)
            if path == "/":
                self._send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
            elif path == "/api/scenes":
                if not p.has("plan.csv"):
                    self._json({"error": "plan.csv not found: run the pipeline up to download first"}, 404)
                    return
                self._json({"title": p.meta.title or p.slug, "slug": p.slug, "scenes": scenes(p)})
            elif path == "/api/translate":
                if not p.has("plan.csv"):
                    self._json({"available": False, "reason": "plan.csv not found", "texts": {}})
                    return
                self._json(translations(p, translator))
            elif path.startswith("/files/"):
                rel = path.removeprefix("/files/")
                target = (p.root / rel).resolve()
                allowed = any(target.is_relative_to((p.root / d).resolve()) for d in SERVED_DIRS)
                if not allowed or not target.is_file():
                    self._send(HTTPStatus.NOT_FOUND, b"not found", "text/plain")
                    return
                kind = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
                self._send(200, target.read_bytes(), kind)
            else:
                self._send(HTTPStatus.NOT_FOUND, b"not found", "text/plain")

        def do_POST(self) -> None:
            if urlparse(self.path).path != "/api/manual":
                self._send(HTTPStatus.NOT_FOUND, b"not found", "text/plain")
                return
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
                scene, url = int(body["scene"]), (body.get("url") or "").strip()
                with _write_lock:
                    if url:
                        set_manual(p, scene, url)
                    else:
                        clear_manual(p, scene)
            except Exception as exc:
                log.warning("scene manual image: %s", exc)
                self._json({"error": str(exc)}, 400)
                return
            row = next((s for s in scenes(p) if s["scene"] == scene), None)
            self._json({"scene": row})

    return Handler


def serve(p: Project, host: str, port: int, translate: bool = True) -> ThreadingHTTPServer:
    translator = Translator(p, get_settings()) if translate else None
    return ThreadingHTTPServer((host, port), make_handler(p, translator))
