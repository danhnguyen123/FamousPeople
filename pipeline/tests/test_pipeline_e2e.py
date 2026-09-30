"""Full runs with Claude and every HTTP API mocked."""

import json

import httpx
from conftest import brief, jpeg_bytes

from docugen import llm, pipeline
from docugen.models import DocumentSubject, PersonFacts
from docugen.project import Project

SCRIPT = """In 1994, Winona Ryder was already one of Hollywood's most recognizable young actresses.
Her performance in Little Women earned her a second Academy Award nomination.
[SHOW RAIN]
But far from the red carpet, the rain kept falling on a quiet California town."""


def commons_page(i: int, title: str) -> dict:
    return {
        "index": i,
        "title": f"File:{title}.jpg",
        "imageinfo": [{
            "mime": "image/jpeg",
            "url": f"https://upload.wikimedia.org/{i}.jpg",
            "thumburl": f"https://upload.wikimedia.org/{i}.jpg",
            "descriptionurl": f"https://commons.wikimedia.org/wiki/File:{i}",
            "width": 2400, "height": 1600,
            "extmetadata": {"ImageDescription": {"value": title},
                            "LicenseShortName": {"value": "CC BY 2.0"},
                            "Artist": {"value": "Alan Light"}},
        }],
    }


def test_script_pipeline_with_archive_sources(tmp_path, settings, mock_http, monkeypatch):
    settings.providers = ["wikimedia", "openverse"]
    monkeypatch.setattr(llm, "identify_subject", lambda script, lang: DocumentSubject(
        main_person="Winona Ryder",
        people=[PersonFacts(name="Winona Ryder", aliases=["Winona Laura Horowitz"], birth_year=1971,
                            death_year=None, notable_works=["Little Women (1994)"])],
        era_from=1990, era_to=1999, title="Winona"))
    monkeypatch.setattr(llm, "write_briefs", lambda scenes, subject, entities, lang: [
        brief(scene_index=0),
        brief(scene_index=1, event_anchor="66th Academy Awards", specific_queries=["Winona Ryder Academy Awards 1994"]),
        brief(scene_index=2, visual_type="generic", primary_entity=None, year_from=None, year_to=None,
              event_anchor=None, location=None, specific_queries=["rain small town street"]),
    ])
    pages = {str(i): commons_page(i, t) for i, t in enumerate([
        "Winona Ryder at the Little Women premiere 1994",
        "Winona Ryder 66th Academy Awards 1994",
        "Rain on a street in a small town",
        "Some other actress 1994",
    ])}
    mock_http["commons.wikimedia.org"] = httpx.Response(200, json={"query": {"pages": pages}})
    mock_http["api.openverse.org"] = httpx.Response(200, json={"results": []})
    for i in range(4):
        mock_http[f"upload.wikimedia.org/{i}.jpg"] = httpx.Response(200, content=jpeg_bytes(pattern=i + 10))

    project = Project.create("winona", "en", SCRIPT, base=settings.projects_dir)
    pipeline.run(project, settings, until="timeline", use_tts=False)

    scenes = json.loads(project.path("scenes.json").read_text())
    assert all("SHOW RAIN" not in s["text"] for s in scenes)
    footage = json.loads(project.path("footage.json").read_text())
    for f in footage[:2]:  # nameless photos stay available but rank below named ones
        titles = [r["candidate"]["title"] for r in f["ranked"]]
        assert len(titles) == 4
        assert all("Winona Ryder" in t for t in titles[:2])
    timeline = json.loads(project.path("timeline.json").read_text())
    assert timeline["title"] == "Winona"
    assert timeline["showCredits"] is False
    assert len(timeline["shots"]) == 3
    assert project.has("review.html") and project.has("credits.txt")
    assert "Alan Light" in project.path("credits.txt").read_text()


SRT = """1
00:00:00,000 --> 00:00:03,000
In 1994, Winona Ryder was already one of the biggest stars in Hollywood.

2
00:00:03,100 --> 00:00:05,000
Her role in Little Women

3
00:00:05,100 --> 00:00:08,000
earned her a second Oscar nomination.
"""


def google_result(i: int, title: str) -> dict:
    return {
        "original": f"https://img.example/{i}.jpg",
        "thumbnail": f"https://encrypted-tbn0.gstatic.com/{i}",
        "original_width": 1600, "original_height": 1000,
        "title": title, "link": f"https://news.example/{i}", "source": "News",
    }


def test_srt_pipeline_with_google(tmp_path, settings, mock_http, monkeypatch):
    monkeypatch.setattr(llm, "identify_subject", lambda script, lang: DocumentSubject(
        main_person="Winona Ryder",
        people=[PersonFacts(name="Winona Ryder", aliases=[], birth_year=1971, death_year=None,
                            notable_works=[])],
        era_from=1990, era_to=1999, title="Winona"))
    monkeypatch.setattr(llm, "write_briefs", lambda scenes, subject, entities, lang: [
        brief(scene_index=s.index, specific_queries=[f"Winona Ryder query {s.index}"]) for s in scenes
    ])
    searches = []

    def serp(request):
        searches.append(request.url.params["q"])
        return httpx.Response(200, json={"images_results": [
            google_result(0, "Winona Ryder Little Women premiere 1994"),
            google_result(1, "Winona Ryder at the Oscars 1994"),
            google_result(2, "Hollywood premiere crowd"),
        ]})

    mock_http["serpapi.com"] = serp
    for i in range(3):
        mock_http[f"img.example/{i}.jpg"] = httpx.Response(
            200, content=jpeg_bytes(pattern=i + 20), headers={"content-type": "image/jpeg"})

    srt = tmp_path / "voice.srt"
    srt.write_text(SRT, encoding="utf-8")
    audio = tmp_path / "voice.wav"
    audio.write_bytes(b"RIFF0000WAVE")
    project = Project.create_from_srt("winona-srt", "en", srt, audio, base=settings.projects_dir)
    pipeline.run(project, settings, until="timeline")

    scenes = json.loads(project.path("scenes.json").read_text())
    assert len(scenes) == 2 and scenes[1]["start"] == 3.1
    timeline = json.loads(project.path("timeline.json").read_text())
    assert timeline["audio"] == [{"src": "projects/winona-srt/audio/narration.wav", "startSec": 0.0}]
    assert timeline["durationSec"] == 8.5
    assert [c["startSec"] for c in timeline["captions"]] == [0.0, 3.1, 5.1]
    assert timeline["shots"][1]["startSec"] == 3.1
    assert project.has("cache/serpapi")

    # A rerun of the search stage is served from the cache: no new searches.
    count = len(searches)
    pipeline.run(project, settings, until="search", force={"search"})
    assert len(searches) == count
