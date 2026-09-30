"""A project folder holds the inputs and every stage's output.

projects/<slug>/
  project.json     language, title, audio path
  input.srt        the subtitles with exact timings
  audio/           the narration audio
  plan.json        stage plan: scenes, groups, keywords (Claude)
  search.json      stage search: results per group from every source
  select.json      stage select: accepted and rejected results per group (Claude)
  images.json      stage download: the image shown in each scene
  assets/          downloaded images
  manual/          put scene_007.jpg here to force an image for scene 7
  plan.csv         one row per scene, for review in a spreadsheet
  candidates.csv   every search result with Claude's verdict
  timeline.json    stage timeline: Remotion props
  cache/           raw search API responses, reused on reruns
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel, TypeAdapter

from .config import get_settings
from .models import Cue
from .srt import parse_srt

T = TypeVar("T")


class ProjectMeta(BaseModel):
    slug: str
    language: str
    title: str | None = None
    audio: str | None = None  # path relative to the project


class Project:
    def __init__(self, root: Path):
        self.root = root
        self.meta = ProjectMeta.model_validate_json((root / "project.json").read_text())

    @classmethod
    def open(cls, slug_or_path: str) -> "Project":
        path = Path(slug_or_path)
        if not (path / "project.json").exists():
            path = get_settings().projects_dir / slug_or_path
        if not (path / "project.json").exists():
            raise FileNotFoundError(f"No project.json in {path}")
        return cls(path)

    @classmethod
    def create_from_srt(
        cls, slug: str, language: str, srt: Path, audio: Path | None, base: Path | None = None
    ) -> "Project":
        content = srt.read_text(encoding="utf-8-sig")
        if not parse_srt(content):
            raise ValueError(f"No subtitle cues found in {srt}")
        root = (base or get_settings().projects_dir) / slug
        root.mkdir(parents=True, exist_ok=True)
        (root / "manual").mkdir(exist_ok=True)
        (root / "input.srt").write_text(content, encoding="utf-8")
        meta = ProjectMeta(slug=slug, language=language)
        if audio is not None:
            target = root / f"audio/narration{audio.suffix.lower()}"
            target.parent.mkdir(exist_ok=True)
            shutil.copy2(audio, target)
            meta.audio = str(target.relative_to(root))
        (root / "project.json").write_text(meta.model_dump_json(indent=2))
        return cls(root)

    @property
    def slug(self) -> str:
        return self.meta.slug

    @property
    def language(self) -> str:
        return self.meta.language

    def cues(self) -> list[Cue]:
        return parse_srt(self.path("input.srt").read_text(encoding="utf-8"))

    def path(self, name: str) -> Path:
        return self.root / name

    def has(self, name: str) -> bool:
        return (self.root / name).exists()

    def save(self, name: str, data: BaseModel | list | dict) -> Path:
        target = self.root / name
        if isinstance(data, BaseModel):
            text = data.model_dump_json(indent=2)
        else:
            text = TypeAdapter(type(data)).dump_json(data, indent=2).decode()
        target.write_text(text, encoding="utf-8")
        return target

    def load(self, name: str, type_: type[T]) -> T:
        return TypeAdapter(type_).validate_json((self.root / name).read_text(encoding="utf-8"))

    def save_meta(self) -> None:
        (self.root / "project.json").write_text(self.meta.model_dump_json(indent=2))
