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
from .pipeline import OUTPUTS, STAGES, run
from .project import Project

app = typer.Typer(add_completion=False, help="SRT + audio to documentary video.")
console = Console()


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(message)s",
        handlers=[RichHandler(console=console, show_path=False)],
    )
    for noisy in ("httpx", "anthropic", "PIL"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "project"


@app.command()
def new(
    srt: Path = typer.Option(..., exists=True, readable=True, help="Subtitles with timings"),
    lang: str = typer.Option(..., "--lang", "-l", help=f"Script language: {', '.join(LANGUAGES)}"),
    audio: Path | None = typer.Option(
        None, exists=True, readable=True, help="Narration audio matching the SRT (mp3, wav, m4a)"
    ),
    slug: str | None = typer.Option(None, help="Project folder name (default: SRT file name)"),
) -> None:
    """Create a project from an SRT and its narration audio."""
    get_language(lang)
    if audio is None:
        console.print("[yellow]No --audio given: the video will be silent[/yellow]")
    project = Project.create_from_srt(slug or _slugify(srt.stem), lang.lower(), srt, audio)
    console.print(f"Created [bold]{project.root}[/bold]")


@app.command("run")
def run_cmd(
    project: str = typer.Argument(..., help="Project slug or folder"),
    until: str = typer.Option("render", help=f"Last stage: {', '.join(STAGES)}"),
    force: list[str] = typer.Option([], "--force", "-f", help="Redo this stage and all after it"),
    captions: bool = typer.Option(False, help="Burn in captions"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Run the pipeline, skipping stages whose output already exists."""
    _setup_logging(verbose)
    for stage in [until, *force]:
        if stage not in STAGES:
            raise typer.BadParameter(f"Unknown stage '{stage}' (stages: {', '.join(STAGES)})")
    p = Project.open(project)
    run(p, get_settings(), until=until, force=set(force), captions=captions)
    if p.has("plan.csv"):
        console.print(f"Review: {p.path('plan.csv')}")


@app.command()
def status(project: str) -> None:
    """Show which stage outputs exist."""
    p = Project.open(project)
    for stage in STAGES:
        name = OUTPUTS.get(stage, f"out/{p.slug}-{p.language}.mp4")
        mark = "[green]done[/green]" if p.has(name) else "[dim]todo[/dim]"
        console.print(f"{mark}  {stage:9} {name}")


if __name__ == "__main__":
    app()
