import httpx

from docugen.providers import SerpApiGoogleImages

RESPONSE = {
    "images_results": [
        {
            "position": 1,
            "thumbnail": "https://encrypted-tbn0.gstatic.com/images?q=1",
            "original": "https://www.vogue.com/photos/ryder-1994.jpg",
            "original_width": 2000,
            "original_height": 1333,
            "title": "Winona Ryder at the Little Women premiere, 1994",
            "link": "https://www.vogue.com/article/winona-ryder-1994",
            "source": "Vogue",
        },
        {"position": 2, "original": "https://shop.example/x.jpg", "is_product": True,
         "link": "https://shop.example/p"},
        {"position": 3, "thumbnail": "https://encrypted-tbn0.gstatic.com/images?q=3"},
    ]
}


def test_serpapi_parsing_and_params(mock_http):
    seen = []

    def handler(request):
        seen.append(dict(request.url.params))
        return httpx.Response(200, json=RESPONSE)

    mock_http["serpapi.com"] = handler
    results = SerpApiGoogleImages("k", language="de", gl="de", tbs="isz:l").search("Winona Ryder 1994")
    assert len(results) == 1  # products and results without an original are skipped
    c = results[0]
    assert c.provider == "google"
    assert c.image_url == "https://www.vogue.com/photos/ryder-1994.jpg"
    assert c.page_url == "https://www.vogue.com/article/winona-ryder-1994"
    assert c.source_domain == "vogue.com"
    assert (c.width, c.height) == (2000, 1333)
    params = seen[0]
    assert params["engine"] == "google_images" and params["hl"] == "de"
    assert params["gl"] == "de" and params["tbs"] == "isz:l" and params["api_key"] == "k"


def test_serpapi_cache(tmp_path, mock_http):
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(200, json=RESPONSE)

    mock_http["serpapi.com"] = handler
    provider = SerpApiGoogleImages("k", cache_dir=tmp_path / "cache")
    first = provider.search("Winona Ryder 1994")
    second = provider.search("Winona Ryder 1994")
    assert len(calls) == 1
    assert first == second
    provider.search("Winona Ryder 1995")
    assert len(calls) == 2


def test_serpapi_no_results_is_empty(mock_http):
    mock_http["serpapi.com"] = httpx.Response(200, json={"error": "Google hasn't returned any results for this query."})
    assert SerpApiGoogleImages("k").search("zzzz") == []
