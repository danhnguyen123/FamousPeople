"""Apply image links pasted on the audit page to a project, the same way `docugen review` does.

The page stores one document per scene in its "manual" collection: {scene, url, at}. Save them
with Claude Code's ArtifactData tool (action "list", collection "manual", out_dir <dir>), then:

Usage: python tools/audit/apply_links.py <slug> <dir>/manual

Each link is downloaded to manual/scene_NNN.jpg, recorded in manual/links.json, and images.json
and plan.csv are rewritten. Rebuild and republish the page afterwards (build_page.py).
"""

import json
import sys
from pathlib import Path

from docugen.project import Project
from docugen.review import set_manual

p = Project.open(sys.argv[1])
docs = sorted(Path(sys.argv[2]).glob("*.json"), key=lambda f: int(f.stem) if f.stem.isdigit() else 0)
for f in docs:
    doc = json.loads(f.read_text(encoding="utf-8"))
    doc = doc.get("data", doc)
    scene, url = int(doc.get("scene") or f.stem), (doc.get("url") or "").strip()
    if not url:
        continue
    try:
        set_manual(p, scene, url)
        print(f"scene {scene}: ok")
    except Exception as exc:
        print(f"scene {scene}: failed ({exc})")
