from docugen.segment import narration_text, normalize_script, segment_script


def test_stage_directions_removed():
    raw = "[SHOW BANK]\nThe robbers approached the bank. [CUT TO MUGSHOT] They wore masks."
    assert normalize_script(raw) == "The robbers approached the bank. They wore masks."


def test_short_sentences_are_merged_and_offsets_match():
    raw = (
        "She was born in 1971. In Minnesota. "
        "By 1994 she was one of the most recognizable young actresses in Hollywood.\n\n"
        "Then everything changed."
    )
    scenes = segment_script(raw, "en", min_chars=30)
    text = narration_text(scenes)
    assert scenes[0].sentences == ["She was born in 1971.", "In Minnesota."]
    for s in scenes:
        assert text[s.char_start : s.char_start + len(s.text)] == s.text


def test_german_abbreviations_do_not_split():
    raw = "Am 29. Oktober 1971 wurde sie geboren, u.a. in Winona. Später zog die Familie nach Kalifornien."
    scenes = segment_script(raw, "de", min_chars=10)
    assert scenes[0].text.startswith("Am 29. Oktober 1971")
    assert len(scenes) == 2


def test_polish_segmentation():
    raw = "W 1994 roku była już gwiazdą. Nikt nie wiedział, co wydarzy się później."
    assert len(segment_script(raw, "pl", min_chars=10)) == 2
