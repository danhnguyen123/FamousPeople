"""Command line: docugen new / run / status."""

from __future__ import annotations

import logging
import re
from pathlib import Path

import typer
from rich.console import Console
from rich.logging import RichHandler

from .config import get_settings
from .languages import LANGUAGES, get_language
from .pipeline import STAGES, run
from .project import Project

app = typer.Typer(add_completion=False, help="Script to keyframe documentary video.")
console = Console()


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(message)s",
        handlers=[RichHandler(console=console, show_path=False)],
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "project"


@app.command()
def new(
    script: Path | None = typer.Argument(
        None, exists=True, readable=True, help="Narration script (.txt); TTS makes the audio"
    ),
    lang: str = typer.Option(..., "--lang", "-l", help=f"One of: {', '.join(LANGUAGES)}"),
    srt: Path | None = typer.Option(
        None, exists=True, readable=True, help="Subtitles with timings (use instead of a script)"
    ),
    audio: Path | None = typer.Option(
        None, exists=True, readable=True, help="Narration audio matching the SRT (mp3, wav, m4a)"
    ),
    slug: str | None = typer.Option(None, help="Project folder name (default: input file name)"),
) -> None:
    """Create a project from a script file, or from an SRT plus its audio."""
    get_language(lang)
    if (script is None) == (srt is None):
        raise typer.BadParameter("Give either a script file or --srt")
    if srt is not None:
        if audio is None:
            console.print("[yellow]No --audio given: the video will be silent[/yellow]")
        project = Project.create_from_srt(slug or _slugify(srt.stem), lang.lower(), srt, audio)
    else:
        assert script is not None
        project = Project.create(
            slug or _slugify(script.stem), lang.lower(), script.read_text(encoding="utf-8")
        )
    console.print(f"Created [bold]{project.root}[/bold]")


@app.command("run")
def run_cmd(
    project: str = typer.Argument(..., help="Project slug or folder"),
    until: str = typer.Option("render", help=f"Last stage: {', '.join(STAGES)}"),
    force: list[str] = typer.Option([], "--force", "-f", help="Redo this stage and all after it"),
    tts: bool = typer.Option(
        True, help="Script projects: use ElevenLabs; --no-tts estimates timings (silent preview)"
    ),
    max_shot: float = typer.Option(6.0, help="Longest time one image stays on screen (seconds)"),
    captions: bool = typer.Option(False, help="Burn in captions"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Run the pipeline, skipping stages whose output already exists."""
    _setup_logging(verbose)
    for stage in [until, *force]:
        if stage not in STAGES:
            raise typer.BadParameter(f"Unknown stage '{stage}'")
    p = Project.open(project)
    run(p, get_settings(), until=until, force=set(force), use_tts=tts, max_shot=max_shot, captions=captions)
    if p.has("review.html"):
        console.print(f"Review: {p.path('review.html')}")


@app.command()
def status(project: str) -> None:
    """Show which stage outputs exist."""
    p = Project.open(project)
    for name in ["scenes.json", "subject.json", "briefs.json", "footage.json", "narration.json",
                 "review.html", "timeline.json"]:
        mark = "[green]done[/green]" if p.has(name) else "[dim]todo[/dim]"
        console.print(f"{mark}  {name}")


if __name__ == "__main__":
    app()
