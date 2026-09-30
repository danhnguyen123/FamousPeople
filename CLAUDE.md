# CLAUDE.md

Script to documentary video tool. Input is an SRT plus its narration audio (or a .txt script with ElevenLabs TTS). Python pipeline (`pipeline/`, package `docugen`) produces `timeline.json`; the Remotion project (`video/`) renders it.

## Commands

- Pipeline tests (offline, all HTTP mocked): `cd pipeline && python -m pytest`
- Remotion typecheck + lint: `cd video && npm run lint`
- Render: `docugen run <slug>` or `cd video && npx remotion render Documentary out.mp4 --props=<timeline.json>`
- In containers where Remotion cannot download Chrome, pass `--browser-executable` (or set `REMOTION_BROWSER_EXECUTABLE`).

## Rules

- `video/src/schema.ts` and `pipeline/src/docugen/timeline.py` describe the same JSON. Change both together.
- Identity of people is scored by metadata (name or alias from Claude's `PersonFacts` in title/source/page URL), never by CLIP. CLIP only reranks.
- No hard filters besides user-blocked domains (`DOCUGEN_BLOCKED_DOMAINS`): missing names, low resolution and watermarks lower the score but never reject a candidate.
- Google Images only through SerpApi (or a similar third-party search API such as DataForSEO). Never write our own scrapers for Google, Pinterest or YouTube.
- Default source is `google` (`DOCUGEN_PROVIDERS`); Wikimedia/Openverse/Pexels/Brave code stays but is off by default. SerpApi responses are cached per project; keep that cache when changing the provider.
- No copyright filtering: `scoring.license_tier` is informational only (review.html, on-screen credits) and must never reject candidates.
- Claude calls live in `pipeline/src/docugen/llm.py` (structured outputs via `client.beta.messages.parse`, model from `DOCUGEN_MODEL`, default `claude-opus-5-5`).
- Narration scripts and example scripts must not contain em dashes.
- For Remotion work, use the skills in `.claude/skills/` (remotion-best-practices first).
