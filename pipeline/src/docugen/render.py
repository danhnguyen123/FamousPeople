"""Stage 8: render the MP4 with the Remotion project in video/."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from .config import Settings


def render(timeline_path: Path, output: Path, settings: Settings) -> Path:
    cmd = [
        "npx", "remotion", "render", "Documentary", str(output.resolve()),
        f"--props={timeline_path.resolve()}",
    ]
    browser = os.environ.get("REMOTION_BROWSER_EXECUTABLE")
    if browser:
        cmd.append(f"--browser-executable={browser}")
    subprocess.run(cmd, cwd=settings.remotion_dir, check=True)
    return output
