"""A project folder holds the script and every stage's JSON output.

projects/<slug>/
  project.json      language, title
  script.txt        the narration (for SRT projects: the cue text joined)
  input.srt         SRT projects only: the subtitles with exact timings
  audio/            SRT projects: the narration audio you supplied
  scenes.json       stage 1  segment
  subject.json      stage 2  subject + facts about the people (Claude)
  briefs.json       stage 3  visual briefs from Claude
  footage.json      stage 4  ranked candidates per scene
  assets/           stage 5  downloaded images
  manual/           put scene_007.jpg here to force an image for scene 7
  narration.json    stage 5  TTS audio (or supplied audio) + scene timings
  timeline.json     stage 7  Remotion props
  review.html       contact sheet for manual review
  credits.txt       attribution text for the video description
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Literal, TypeVar

from pydantic import BaseModel, TypeAdapter

from .config import get_settings

T = TypeVar("T")


class ProjectMeta(BaseModel):
    slug: str
    language: str
    title: str | None = None
    source: Literal["script", "srt"] = "script"
    audio: str | None = None  # path relative to the project, SRT projects only


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
    def create(cls, slug: str, language: str, script: str, base: Path | None = None) -> "Project":
        root = (base or get_settings().projects_dir) / slug
        root.mkdir(parents=True, exist_ok=True)
        (root / "manual").mkdir(exist_ok=True)
        (root / "script.txt").write_text(script, encoding="utf-8")
        meta = ProjectMeta(slug=slug, language=language)
        (root / "project.json").write_text(meta.model_dump_json(indent=2))
        return cls(root)

    @classmethod
    def create_from_srt(
        cls, slug: str, language: str, srt: Path, audio: Path | None, base: Path | None = None
    ) -> "Project":
        from .srt import parse_srt, srt_text

        srt_content = srt.read_text(encoding="utf-8-sig")
        cues = parse_srt(srt_content)
        if not cues:
            raise ValueError(f"No subtitle cues found in {srt}")
        project = cls.create(slug, language, srt_text(cues), base=base)
        project.path("input.srt").write_text(srt_content, encoding="utf-8")
        project.meta.source = "srt"
        if audio is not None:
            target = project.path(f"audio/narration{audio.suffix.lower()}")
            target.parent.mkdir(exist_ok=True)
            shutil.copy2(audio, target)
            project.meta.audio = str(target.relative_to(project.root))
        project.save_meta()
        return project

    @property
    def slug(self) -> str:
        return self.meta.slug

    @property
    def language(self) -> str:
        return self.meta.language

    def script(self) -> str:
        return (self.root / "script.txt").read_text(encoding="utf-8")

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


def write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
