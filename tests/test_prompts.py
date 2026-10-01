from vidbrief import prompts

COMPLETE = """## Executive Summary
Hello.

## Speaker & Guests
- A

## Thematic Breakdown
### Section 1: One
- [00:00:10] a
### Section 2: Two
- [00:10:00] b
### Section 3: Three
- [00:20:00] c
- [00:25:00] d
- [00:28:00] e
- [00:29:00] f

## Key Takeaways
- x
"""


def test_complete_structure():
    ok, missing = prompts.validate_summary_structure(COMPLETE)
    assert ok, missing


def test_incomplete():
    ok, missing = prompts.validate_summary_structure("just a paragraph")
    assert not ok
    assert "Executive Summary" in missing


def test_default_prompts_exist():
    for name in prompts.NAMES:
        assert prompts.load_prompt(name)


def test_private_override_wins(tmp_path):
    (tmp_path / "private").mkdir()
    (tmp_path / "extract.md").write_text("public")
    (tmp_path / "private" / "extract.md").write_text("mine")
    assert prompts.load_prompt("extract", prompts_dir=tmp_path) == "mine"
    (tmp_path / "private" / "extract.md").unlink()
    assert prompts.load_prompt("extract", prompts_dir=tmp_path) == "public"


def test_synthesis_prompt_asks_for_validated_headings():
    text = prompts.load_prompt("synthesize").lower()
    assert "### section x:" in text
    assert "## key takeaways" in text


def test_missing_timestamps_flagged():
    import re

    no_ts = re.sub(r"\[\d\d:\d\d:\d\d\] ", "", COMPLETE)
    ok, missing = prompts.validate_summary_structure(no_ts)
    assert not ok
    assert any("timestamps" in m for m in missing)


def test_too_many_sections_flagged():
    body = "\n".join(f"### Section {i}: T\n- [00:0{i % 10}:00] a\n- [00:0{i % 10}:30] b" for i in range(1, 15))
    text = f"## Executive Summary\nx\n## Thematic Breakdown\n{body}\n## Key Takeaways\n- y\n"
    ok, missing = prompts.validate_summary_structure(text)
    assert not ok
    assert any("at most" in m for m in missing)


def test_section_count_scales_with_length():
    assert prompts.section_count(10 * 60) == 3
    assert prompts.section_count(60 * 60) == 4
    assert prompts.section_count(3 * 3600) == 6


def test_format_reminder_after_content():
    text = prompts.synthesize_user_prompt(title="T", uploader=None, condensed="BODY", sections=5)
    assert text.index("BODY") < text.index("exactly 5 chapters")


def test_section_spans_cover_whole_video():
    spans = prompts.section_spans(5280, 6)
    assert spans[0][0] == "00:00:00"
    assert spans[-1][1] == "01:28:00"
    assert len(spans) == 6
