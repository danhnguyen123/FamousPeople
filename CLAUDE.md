# CLAUDE.md

Script to documentary video tool. Python pipeline (`pipeline/`, package `docugen`) produces `timeline.json`; the Remotion project (`video/`) renders it.

## Commands

- Pipeline tests (offline, all HTTP mocked): `cd pipeline && python -m pytest`
- Remotion typecheck + lint: `cd video && npm run lint`
- Render: `docugen run <slug>` or `cd video && npx remotion render Documentary out.mp4 --props=<timeline.json>`
- In containers where Remotion cannot download Chrome, pass `--browser-executable` (or set `REMOTION_BROWSER_EXECUTABLE`).

## Rules

- `video/src/schema.ts` and `pipeline/src/docugen/timeline.py` describe the same JSON. Change both together.
- Identity of people is decided by metadata (name or Wikidata alias in title/caption/categories), never by CLIP. CLIP only reranks.
- Never add scrapers for Pinterest, Google Images or YouTube. New sources go through official APIs and must set a license tier in `scoring.license_tier`.
- Claude calls live in `pipeline/src/docugen/llm.py` (structured outputs via `client.beta.messages.parse`, model from `DOCUGEN_MODEL`, default `claude-opus-5-5`).
- Narration scripts and example scripts must not contain em dashes.
- For Remotion work, use the skills in `.claude/skills/` (remotion-best-practices first).
