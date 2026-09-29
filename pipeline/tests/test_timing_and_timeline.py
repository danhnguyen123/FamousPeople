import json

import httpx
from conftest import brief, cand, jpeg_bytes

from docugen.models import NarrationTrack, SceneFootage, SceneTiming
from docugen.project import Project
from docugen.scoring import score_candidate
from docugen.segment import segment_script
from docugen.select_images import select_images, shots_needed
from docugen.timeline import build_timeline
from docugen.tts import chunk_scenes, estimate, make_continuous, scene_times_from_alignment

SCRIPT = (
    "In 1994, Winona Ryder was already one of Hollywood's most recognizable young actresses. "
    "Her role in Little Women earned her a second Academy Award nomination. "
    "But behind the flashbulbs, the pressure was building."
)


def test_alignment_maps_scene_boundaries():
    scenes = segment_script(SCRIPT, "en", min_chars=20)
    text = " ".join(s.text for s in scenes)
    starts = [i * 0.05 for i in range(len(text))]
    ends = [s + 0.05 for s in starts]
    times = scene_times_from_alignment(scenes, starts, ends)
    assert times[0][1] == 0.0
    assert abs(times[1][1] - scenes[1].char_start * 0.05) < 1e-9
    timings = make_continuous(times, 20.0)
    assert timings[0].end == timings[1].start
    assert timings[-1].end == 20.0


def test_chunking_keeps_scenes_whole():
    scenes = segment_script(SCRIPT * 20, "en", min_chars=20)
    chunks = chunk_scenes(scenes, max_chars=500)
    assert sum(len(c) for c in chunks) == len(scenes)
    assert all(sum(len(s.text) + 1 for s in c) <= 500 + max(len(s.text) for s in c) for c in chunks)


def test_estimate_uses_language_rate():
    scenes = segment_script(SCRIPT, "en", min_chars=20)
    en = estimate(scenes, "en").duration
    pl = estimate(scenes, "pl").duration
    assert pl > en > 5


def test_shots_needed():
    assert shots_needed(4, 6) == 1
    assert shots_needed(6.5, 6) == 1
    assert shots_needed(13, 6) == 3


def test_select_and_timeline(tmp_path, settings, ryder, mock_http):
    project = Project.create("demo", "en", SCRIPT, base=tmp_path / "projects")
    scenes = segment_script(SCRIPT, "en", min_chars=20)
    b = brief()
    a = score_candidate(cand(image_url="https://img/a.jpg"), b, ryder, settings)
    dup = score_candidate(cand(image_url="https://img/dup.jpg"), b, ryder, settings)
    c = score_candidate(cand(image_url="https://img/c.jpg", license="Public domain"), b, ryder, settings)
    mock_http["img/a.jpg"] = httpx.Response(200, content=jpeg_bytes(pattern=0))
    mock_http["img/dup.jpg"] = httpx.Response(200, content=jpeg_bytes(pattern=0))
    mock_http["img/c.jpg"] = httpx.Response(200, content=jpeg_bytes(color=(10, 10, 60), pattern=3))

    footage = [
        SceneFootage(scene_index=0, ranked=[a, dup, c]),
        SceneFootage(scene_index=1, ranked=[a]),  # only an already used image: reused
        SceneFootage(scene_index=2, ranked=[]),  # nothing found: previous shot is held
    ]
    narration = NarrationTrack(
        audio_files=[],
        scenes=[SceneTiming(scene_index=0, start=0, end=10),
                SceneTiming(scene_index=1, start=10, end=14),
                SceneTiming(scene_index=2, start=14, end=18)],
        duration=18,
    )
    footage = select_images(project, footage, narration, max_shot=6)
    assert footage[0].chosen == [a.candidate.id, c.candidate.id]  # duplicate skipped by phash
    assert footage[1].chosen == [a.candidate.id]

    timeline = build_timeline(project, scenes, footage, narration, settings, title="Demo")
    shots = timeline["shots"]
    assert [s["startSec"] for s in shots] == [0.0, 5.0, 10.0]
    assert shots[-1]["endSec"] == 18
    assert shots[0]["credit"].startswith("Photo: ")
    assert shots[1]["credit"] is None  # public domain needs no credit
    for shot in shots:
        assert (settings.remotion_dir / "public" / shot["src"]).exists()
    json.dumps(timeline)


def test_manual_override(tmp_path, settings):
    project = Project.create("demo", "en", SCRIPT, base=tmp_path / "projects")
    (project.path("manual") / "scene_000.jpg").write_bytes(jpeg_bytes())
    footage = select_images(
        project,
        [SceneFootage(scene_index=0, ranked=[])],
        NarrationTrack(audio_files=[], scenes=[SceneTiming(scene_index=0, start=0, end=4)], duration=4),
    )
    assert footage[0].manual and footage[0].local_files["manual-0"] == "manual/scene_000.jpg"
