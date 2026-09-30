"""Full run with Claude and every HTTP API mocked."""

import json

import httpx
from conftest import brief, jpeg_bytes

from docugen import llm, pipeline
from docugen.models import DocumentSubject
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


def test_full_pipeline(tmp_path, settings, mock_http, monkeypatch):
    monkeypatch.setattr(llm, "identify_subject", lambda script, lang: DocumentSubject(
        main_person="Winona Ryder", wikipedia_title="Winona Ryder", other_people=[],
        era_from=1990, era_to=1999, title="Winona"))
    monkeypatch.setattr(llm, "write_briefs", lambda scenes, subject, entities, lang: [
        brief(scene_index=0),
        brief(scene_index=1, event_anchor="66th Academy Awards", specific_queries=["Winona Ryder Academy Awards 1994"]),
        brief(scene_index=2, visual_type="generic", primary_entity=None, year_from=None, year_to=None,
              event_anchor=None, location=None, specific_queries=["rain small town street"]),
    ])
    mock_http["wbgetentities"] = httpx.Response(200, json={"entities": {"Q1": {
        "id": "Q1", "labels": {"en": {"value": "Winona Ryder"}},
        "claims": {"P31": [{"mainsnak": {"datavalue": {"value": {"id": "Q5"}}}}],
                   "P373": [{"mainsnak": {"datavalue": {"value": "Winona Ryder"}}}]}}}})
    mock_http["query.wikidata.org"] = httpx.Response(200, json={"results": {"bindings": []}})
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
