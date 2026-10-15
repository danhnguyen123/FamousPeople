"""One-file HTML audit page for a project: tab 1 groups flagged images, tab 2 is the scene timeline.

Usage: python tools/audit/build_page.py projects/<slug> out/<slug>-audit.html
Reads plan.csv, audit.json, input.srt, project.json, translations.json and manual/links.json.
The page is published as a claude.ai Artifact with capabilities {"db": {}}: pasted links go to
its "manual" collection (one document per scene: {scene, url, at}).
"""
import base64, csv, io, json, sys
from pathlib import Path
from PIL import Image, ImageOps

proj, out = Path(sys.argv[1]), Path(sys.argv[2])
rows = list(csv.DictReader((proj / "plan.csv").open(encoding="utf-8-sig")))
audit = json.loads((proj / "audit.json").read_text(encoding="utf-8"))["scenes"]
from docugen.srt import parse_srt
cues = parse_srt((proj / "input.srt").read_text(encoding="utf-8"))
starts = [float(r["Start"] or 0) for r in rows]
ends = starts[1:] + [cues[-1].end + 0.5]
title = json.loads((proj / "project.json").read_text(encoding="utf-8")).get("title") or proj.name

tr = proj / "translations.json"
vi = json.loads(tr.read_text(encoding="utf-8")) if tr.exists() else {}
vi = vi.get("texts", vi) if isinstance(vi, dict) else {}
links_path = proj / "manual" / "links.json"
manual = json.loads(links_path.read_text(encoding="utf-8")) if links_path.exists() else {}
scenes = []
imgs = {}  # file -> data URI, so an image used by several scenes is embedded once
for i, r in enumerate(rows):
    f = r["Image file"]
    thumb = ""
    if f in imgs:
        thumb = imgs[f]
    elif f and not f.startswith("("):
        try:
            im = ImageOps.contain(Image.open(proj / f).convert("RGB"), (300, 220))
            buf = io.BytesIO(); im.save(buf, "JPEG", quality=62)
            thumb = imgs[f] = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
        except Exception:
            pass
    a = audit.get(r["Scene"])
    scenes.append({
        "n": int(r["Scene"]), "t": starts[i], "e": ends[i], "cues": r["Cues"], "ctx": r["Context"], "text": r["Text"], "g": r["Group"],
        "subject": r["Subject"], "kw": r["Keywords"], "searched": r.get("Searched", ""), "query": r.get("Query", ""), "src": r["Source"], "url": r["Page URL"],
        "reused": r["Reused"] == "yes", "img": f if thumb else "", "file": f,
        "manual_url": manual.get(r["Scene"]), "issue": a["issue"] if a else None, "note": a["note"] if a else None,
    })

page = (Path(__file__).parent / "audit_template.html").read_text(encoding="utf-8")
page = page.replace("__TITLE__", title).replace("__DATA__", json.dumps(scenes, ensure_ascii=False).replace("</", "<\\/")).replace("__IMGS__", json.dumps(imgs)).replace("__VI__", json.dumps(vi, ensure_ascii=False).replace("</", "<\\/"))
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(page, encoding="utf-8")
print(len(scenes), "scenes,", round(out.stat().st_size / 1e6, 1), "MB")
