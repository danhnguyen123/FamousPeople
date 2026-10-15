"""Contact sheets of every scene image, 56 per sheet, scene number in a yellow box.

Usage: python tools/audit/contact_sheets.py projects/<slug> projects/<slug>/sheets
Open the sheets with Claude Code's Read tool to look at them, then write projects/<slug>/audit.json.
"""
import json, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps

proj = Path(sys.argv[1]); out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
data = json.loads((proj / "images.json").read_text())
scenes = data["scenes"] if isinstance(data, dict) and "scenes" in data else data
COLS, ROWS, W, H = 8, 7, 250, 190
font = ImageFont.load_default(size=22)
per = COLS * ROWS
for s in range(0, len(scenes), per):
    sheet = Image.new("RGB", (COLS * W, ROWS * H), "white")
    d = ImageDraw.Draw(sheet)
    for i, sc in enumerate(scenes[s:s + per]):
        x, y = (i % COLS) * W, (i // COLS) * H
        f = sc.get("file") or sc.get("image")
        try:
            im = Image.open(proj / f).convert("RGB")
            im = ImageOps.contain(im, (W - 4, H - 4))
            sheet.paste(im, (x + (W - im.width) // 2, y + (H - im.height) // 2))
        except Exception:
            d.rectangle([x + 2, y + 2, x + W - 3, y + H - 3], fill="#f88")
        n = str(sc.get("scene", s + i + 1))
        d.rectangle([x, y, x + 14 * len(n) + 6, y + 26], fill="yellow")
        d.text((x + 3, y + 1), n, fill="black", font=font)
    sheet.save(out / f"sheet_{s // per + 1:02d}.jpg", quality=80)
print("ok")
