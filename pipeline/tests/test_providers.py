import httpx

from docugen import wikidata
from docugen.providers import Openverse, WikimediaCommons

COMMONS = {
    "query": {
        "pages": {
            "1": {
                "index": 2,
                "title": "File:Winona Ryder 1994.jpg",
                "imageinfo": [{
                    "mime": "image/jpeg",
                    "url": "https://upload.wikimedia.org/o.jpg",
                    "thumburl": "https://upload.wikimedia.org/t.jpg",
                    "descriptionurl": "https://commons.wikimedia.org/wiki/File:Winona_Ryder_1994.jpg",
                    "width": 3000, "height": 2000,
                    "extmetadata": {
                        "ImageDescription": {"value": "<p>Winona Ryder at the <b>Little Women</b> premiere</p>"},
                        "LicenseShortName": {"value": "CC BY-SA 3.0"},
                        "Artist": {"value": "<a href='x'>Alan Light</a>"},
                        "Categories": {"value": "Winona Ryder in 1994|Little Women (1994 film)"},
                        "DateTimeOriginal": {"value": "1994-12-18"},
                    },
                }],
            },
            "2": {"index": 1, "title": "File:Logo.svg", "imageinfo": [{"mime": "image/svg+xml", "url": "x"}]},
        }
    }
}


def test_wikimedia_parsing(mock_http):
    mock_http["commons.wikimedia.org"] = httpx.Response(200, json=COMMONS)
    results = WikimediaCommons().search("Winona Ryder 1994")
    assert len(results) == 1  # svg dropped
    c = results[0]
    assert c.image_url == "https://upload.wikimedia.org/t.jpg"
    assert c.description == "Winona Ryder at the Little Women premiere"
    assert c.author == "Alan Light"
    assert "Winona Ryder in 1994" in c.categories
    assert c.license == "CC BY-SA 3.0"


def test_openverse_parsing(mock_http):
    mock_http["api.openverse.org"] = httpx.Response(200, json={"results": [{
        "url": "https://live.staticflickr.com/x.jpg", "title": "Winona", "creator": "someone",
        "license": "by", "license_version": "2.0", "foreign_landing_url": "https://www.flickr.com/photos/1",
        "width": 1024, "height": 768, "tags": [{"name": "actress"}],
    }]})
    c = Openverse().search("Winona Ryder")[0]
    assert c.license == "CC BY 2.0"
    assert c.source_domain == "flickr.com"
    assert c.tags == ["actress"]


def test_wikidata_resolution(mock_http):
    entity = {
        "id": "Q106997",
        "labels": {"en": {"value": "Winona Ryder"}, "de": {"value": "Winona Ryder"}},
        "aliases": {"en": [{"value": "Winona Laura Horowitz"}]},
        "descriptions": {"en": {"value": "American actress"}},
        "claims": {
            "P31": [{"mainsnak": {"datavalue": {"value": {"id": "Q5"}}}}],
            "P569": [{"mainsnak": {"datavalue": {"value": {"time": "+1971-10-29T00:00:00Z"}}}}],
            "P373": [{"mainsnak": {"datavalue": {"value": "Winona Ryder"}}}],
        },
    }
    mock_http["query.wikidata.org"] = httpx.Response(200, json={"results": {"bindings": [
        {"workLabel": {"value": "Beetlejuice"}, "year": {"value": "1988"}},
        {"workLabel": {"value": "Q123"}},
    ]}})
    mock_http["wbgetentities"] = httpx.Response(200, json={"entities": {"Q106997": entity}})
    info = wikidata.resolve_person("Winona Ryder", "Winona Ryder")
    assert info.qid == "Q106997"
    assert info.birth_year == 1971
    assert info.commons_category == "Winona Ryder"
    assert "Winona Laura Horowitz" in info.aliases
    assert info.notable_works == ["Beetlejuice (1988)"]
