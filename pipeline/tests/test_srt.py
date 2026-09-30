from docugen.srt import group_cues, parse_srt

SRT = "﻿1\r\n00:00:00,000 --> 00:00:02,500\r\n<i>In 1994, Winona Ryder</i>\r\nwas already a star.\r\n\r\n" \
      "2\r\n00:00:02,600 --> 00:00:04,000\r\n{\\an8}Her role in Little Women\r\n\r\n" \
      "3\r\n00:00:04.100 --> 00:00:06.900\r\nearned her a second Oscar nomination.\r\n\r\n" \
      "4\r\n00:00:07,000 --> 00:00:09,000\r\nThen everything changed.\r\n"


def test_parse_srt():
    cues = parse_srt(SRT)
    assert [c.text for c in cues] == [
        "In 1994, Winona Ryder was already a star.",
        "Her role in Little Women",
        "earned her a second Oscar nomination.",
        "Then everything changed.",
    ]
    assert cues[0].start == 0.0 and cues[0].end == 2.5
    assert cues[2].start == 4.1 and cues[2].end == 6.9


def test_group_cues_closes_on_sentence_end():
    scenes = group_cues(parse_srt(SRT), min_chars=30)
    assert [len(s.cues) for s in scenes] == [1, 2, 1]
    assert scenes[1].text == "Her role in Little Women earned her a second Oscar nomination."
    assert (scenes[1].start, scenes[1].end) == (2.6, 6.9)


def test_group_cues_respects_max_duration():
    cues = parse_srt(SRT)
    for c in cues:
        c.text = c.text.rstrip(".") + ","  # no sentence end anywhere
    scenes = group_cues(cues, min_chars=10, max_sec=5)
    assert all(s.end - s.start <= 5 for s in scenes)
    assert sum(len(s.cues) for s in scenes) == 4


def test_ignores_garbage_blocks():
    assert parse_srt("hello\n\nnot a cue") == []
