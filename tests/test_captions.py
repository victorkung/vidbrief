import json

from vidbrief import media


def test_parse_json3_skips_appends_and_noise(tmp_path):
    path = tmp_path / "c.json3"
    path.write_text(json.dumps({"events": [
        {"tStartMs": 0, "dDurationMs": 999999},
        {"tStartMs": 654, "dDurationMs": 2020, "segs": [{"utf8": "[music]"}]},
        {"tStartMs": 7850, "aAppend": 1, "segs": [{"utf8": "\n"}]},
        {"tStartMs": 10240, "dDurationMs": 4880, "segs": [{"utf8": ">> Welcome to the"}, {"utf8": " report."}]},
        {"tStartMs": 15120, "dDurationMs": 1000, "segs": [{"utf8": "It is\nAugust 5th."}]},
    ]}))
    assert media._parse_json3(path) == [
        {"start": 10.24, "end": 15.12, "text": ">> Welcome to the report."},
        {"start": 15.12, "end": 16.12, "text": "It is August 5th."},
    ]


def test_captions_only_for_youtube(tmp_path):
    assert media.fetch_youtube_captions("https://x.com/a/status/1", tmp_path / "t.json") is None
