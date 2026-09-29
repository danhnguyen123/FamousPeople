from conftest import brief

from docugen.queries import commons_categories, find_entity, specific_queries


def test_commons_year_categories(ryder):
    cats = commons_categories(brief(year_from=1993, year_to=1995), ryder)
    assert cats[0] == "Winona Ryder in 1994"
    assert set(cats[:3]) == {"Winona Ryder in 1993", "Winona Ryder in 1994", "Winona Ryder in 1995"}
    assert cats[-1] == "Winona Ryder"


def test_no_categories_for_places(ryder):
    assert commons_categories(brief(visual_type="place"), ryder) == []


def test_find_entity_by_alias(ryder):
    assert find_entity("winona laura horowitz", [ryder]) is ryder
    assert find_entity("Johnny Depp", [ryder]) is None


def test_queries_deduplicated():
    b = brief(specific_queries=["Winona Ryder 1994", "winona ryder 1994"], native_queries=["Winona Ryder 1994 Premiere"])
    assert specific_queries(b) == ["Winona Ryder 1994", "Winona Ryder 1994 Premiere"]
