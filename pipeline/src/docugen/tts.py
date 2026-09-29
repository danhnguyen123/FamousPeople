"""Stage 5: narration audio and per-scene timings.

ElevenLabs /with-timestamps returns the start and end time of every
character, so each scene's exact start and end come for free. Without an API
key the durations are estimated from the language's speaking rate, which is
enough to preview the edit in Remotion Studio.
"""

from __future__ import annotations

import base64

from .config import Settings
from .http import client
from .languages import get_language
from .models import NarrationTrack, Scene, SceneTiming
from .project import Project

API = "https://api.elevenlabs.io/v1/text-to-speech/{voice}/with-timestamps"
MAX_CHUNK_CHARS = 2500
CHUNK_TAIL = 0.35  # silence kept after the last character of a chunk
PAUSE_ESTIMATE = 0.35


def chunk_scenes(scenes: list[Scene], max_chars: int = MAX_CHUNK_CHARS) -> list[list[Scene]]:
    chunks: list[list[Scene]] = [[]]
    for scene in scenes:
        size = sum(len(s.text) + 1 for s in chunks[-1])
        if chunks[-1] and size + len(scene.text) > max_chars:
            chunks.append([])
        chunks[-1].append(scene)
    return [c for c in chunks if c]


def estimate(scenes: list[Scene], language: str) -> NarrationTrack:
    wpm = get_language(language).words_per_minute
    timings, cursor = [], 0.0
    for scene in scenes:
        duration = len(scene.text.split()) / wpm * 60 + PAUSE_ESTIMATE
        timings.append(SceneTiming(scene_index=scene.index, start=cursor, end=cursor + duration))
        cursor += duration
    return NarrationTrack(audio_files=[], scenes=timings, duration=cursor, estimated=True)


def scene_times_from_alignment(
    chunk: list[Scene], starts: list[float], ends: list[float]
) -> list[tuple[int, float, float]]:
    """Map each scene of a chunk to (index, start, end) using character times."""
    out, offset = [], 0
    last = len(starts) - 1
    for scene in chunk:
        first_char = min(offset, last)
        last_char = min(offset + len(scene.text) - 1, last)
        out.append((scene.index, starts[first_char], ends[last_char]))
        offset += len(scene.text) + 1
    return out


def make_continuous(times: list[tuple[int, float, float]], total: float) -> list[SceneTiming]:
    """Close the gaps so every frame belongs to a scene (cuts land on speech starts)."""
    timings = []
    for i, (index, start, _end) in enumerate(times):
        start = 0.0 if i == 0 else start
        end = times[i + 1][1] if i + 1 < len(times) else total
        timings.append(SceneTiming(scene_index=index, start=start, end=max(end, start + 0.1)))
    return timings


def synthesize(project: Project, scenes: list[Scene], settings: Settings) -> NarrationTrack:
    voice = settings.elevenlabs_voice(project.language)
    if not settings.elevenlabs_api_key or not voice:
        raise RuntimeError("Set ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID (or ELEVENLABS_VOICE_<LANG>)")

    chunks = chunk_scenes(scenes)
    audio_dir = project.path("audio")
    audio_dir.mkdir(exist_ok=True)
    files: list[tuple[str, float]] = []
    times: list[tuple[int, float, float]] = []
    cursor = 0.0

    for n, chunk in enumerate(chunks):
        text = " ".join(s.text for s in chunk)
        body: dict = {"text": text, "model_id": settings.elevenlabs_model}
        if n > 0:
            body["previous_text"] = " ".join(s.text for s in chunks[n - 1])[-1000:]
        if n + 1 < len(chunks):
            body["next_text"] = " ".join(s.text for s in chunks[n + 1])[:1000]
        if settings.elevenlabs_model != "eleven_multilingual_v2":
            body["language_code"] = project.language
        response = client().post(
            API.format(voice=voice),
            params={"output_format": "mp3_44100_128"},
            headers={"xi-api-key": settings.elevenlabs_api_key},
            json=body,
            timeout=180,
        )
        response.raise_for_status()
        data = response.json()
        path = audio_dir / f"narration_{n:02d}.mp3"
        path.write_bytes(base64.b64decode(data["audio_base64"]))
        files.append((str(path.relative_to(project.root)), cursor))

        align = data["alignment"]
        starts = align["character_start_times_seconds"]
        ends = align["character_end_times_seconds"]
        for index, start, end in scene_times_from_alignment(chunk, starts, ends):
            times.append((index, cursor + start, cursor + end))
        cursor += (ends[-1] if ends else 0.0) + CHUNK_TAIL

    return NarrationTrack(audio_files=files, scenes=make_continuous(times, cursor), duration=cursor)
