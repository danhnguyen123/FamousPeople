# CLAUDE.md

SRT to documentary video tool. Input is an SRT plus its narration audio. The Python pipeline (`pipeline/`, package `docugen`) runs plan, search, select, download and timeline; the Remotion project (`video/`) renders `timeline.json`. Details: `docs/PIPELINE.md`.

## Commands

- Install: `cd pipeline && pip install -e .`
- Remotion typecheck + lint: `cd video && npm run lint`
- Run: `docugen new --srt x.srt --audio x.mp3 --lang de`, then `docugen run <slug>`
- Render only: `cd video && npx remotion render Documentary out.mp4 --props=<timeline.json>`
- In containers where Remotion cannot download Chrome, pass `--browser-executable` (or set `REMOTION_BROWSER_EXECUTABLE`).
- There are no unit tests. Check changes with a dry run: a hand-written `plan.json` and the search APIs mocked through `docugen.http.set_client` with an `httpx.MockTransport`.

## Rules

- Prompts live in `pipeline/src/docugen/prompts/` (`keyword_planner.md` for the plan, `image_selector.md` for the select step). To change how scenes, groups, keywords or image checks work, edit the prompt, not the code.
- Claude calls live in `pipeline/src/docugen/llm.py`: structured outputs, streaming, `fallbacks: "default"` with beta `server-side-fallback-2026-07-01`. Model from `DOCUGEN_MODEL` / `DOCUGEN_SELECT_MODEL`, default `claude-opus-5-5`.
- `video/src/schema.ts` and `pipeline/src/docugen/timeline.py` describe the same JSON. Change both together.
- Identity is judged from metadata (name in the title or site name), by Claude in the select step. Never by face recognition.
- Image search only through third-party APIs: DataForSEO (Google), SearchAPI.io (Google and Bing), Brave. Never write scrapers for Google, Bing, Pinterest or YouTube. Keep the per-project search cache (`projects/<slug>/cache/`) when changing a source.
- No copyright filtering. The only hard filters are `DOCUGEN_BLOCKED_DOMAINS`, YouTube and TikTok video thumbnails, and failed downloads. Small and duplicate images are kept.
- Narration scripts and prompts must not contain em dashes.
- For Remotion work, use the skills in `.claude/skills/` (remotion-best-practices first).
