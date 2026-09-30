from conftest import brief, cand

from docugen.models import EntityInfo
from docugen.scoring import license_tier, normalize, score_candidate


def test_normalize_strips_accents():
    assert normalize("Édith Piaf, Łódź") == " edith piaf lodz "


def test_name_in_metadata_scores_high(settings, ryder):
    s = score_candidate(cand(), brief(), ryder, settings)
    assert s.rejected_reason is None
    assert s.scores["entity"] == 1.0
    assert s.scores["context"] > 0.8
    assert s.total > 0.75


def test_alias_counts_as_identity(settings, ryder):
    s = score_candidate(cand(title="Portrait of Winona Laura Horowitz, 1994"), brief(), ryder, settings)
    assert s.scores["entity"] == 1.0


def test_wrong_decade_scores_lower(settings, ryder):
    right = score_candidate(cand(), brief(), ryder, settings)
    wrong = score_candidate(cand(title="Winona Ryder in 2016"), brief(), ryder, settings)
    assert wrong.total < right.total


def test_generic_scene_accepts_stock(settings):
    b = brief(visual_type="generic", primary_entity=None, year_from=None, year_to=None,
              event_anchor=None, location=None)
    s = score_candidate(
        cand(provider="pexels", title="rain on a window", license="Pexels License",
             source_domain="pexels.com"), b, None, settings)
    assert s.rejected_reason is None
    assert s.license_tier == "cleared"


def test_license_tiers():
    assert license_tier(cand(license="Public domain")) == "cleared"
    assert license_tier(cand(license="CC0")) == "cleared"
    assert license_tier(cand(license="CC BY 2.0")) == "attribution"
    assert license_tier(cand(license="CC BY-SA 4.0")) == "attribution"
    assert license_tier(cand(license="CC BY-NC 2.0")) == "review"
    assert license_tier(cand(license="Fair use")) == "review"
    assert license_tier(cand(provider="web", license=None)) == "unknown"


def test_web_results_are_accepted(settings, ryder):
    s = score_candidate(cand(provider="web", license=None, source_domain="pinterest.com"),
                        brief(), ryder, settings)
    assert s.rejected_reason is None and s.license_tier == "unknown"


def test_non_free_license_is_not_filtered(settings, ryder):
    s = score_candidate(cand(license="CC BY-NC 2.0"), brief(), ryder, settings)
    assert s.rejected_reason is None


def test_nameless_photo_ranks_below_named_one(settings, ryder):
    named = score_candidate(cand(), brief(), ryder, settings)
    nameless = score_candidate(cand(title="Actress at a premiere, 1994"), brief(), ryder, settings)
    lookalike = score_candidate(cand(title="Jennifer Connelly at a premiere 1994"), brief(), ryder, settings)
    assert nameless.rejected_reason is None and lookalike.rejected_reason is None
    assert named.total > nameless.total + 0.3
    assert named.total > lookalike.total + 0.3


def test_only_blocked_domains_are_rejected(settings, ryder):
    for c in [cand(provider="web", source_domain="gettyimages.com"), cand(width=300, height=380),
              cand(provider="pexels", license="Pexels License")]:
        assert score_candidate(c, brief(), ryder, settings).rejected_reason is None
    settings.blocked_domains = ["fandom.com"]
    s = score_candidate(cand(provider="web", source_domain="x.fandom.com"), brief(), ryder, settings)
    assert s.rejected_reason == "blocked domain"


def test_entity_names_longest_first():
    e = EntityInfo(name="Madonna", aliases=["Madonna Louise Ciccone", "Madonna"])
    assert e.names() == ["Madonna Louise Ciccone", "Madonna"]
