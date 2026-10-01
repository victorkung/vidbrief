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


def test_parse_points_accepts_timestamp_styles():
    text = "[00:01:00] one\n**00:02:30** two\n- [1:03:05] three\nnot a point"
    assert prompts.parse_points(text) == [(60, "one"), (150, "two"), (3785, "three")]


def test_parse_outline_sorts_dedupes_and_starts_at_zero():
    text = "[00:00:05] Intro Topic\n[00:30:00] Later\n[00:12:00] Middle\n[00:12:00] Dup\n[02:00:00] Past end"
    assert prompts.parse_outline(text, 3600) == [(0, "Intro Topic"), (720, "Middle"), (1800, "Later")]


def test_outline_problems_flags_imbalance_and_count():
    assert prompts.outline_problems([(0, "a"), (60, "b"), (120, "c")], 3600, 4)  # last covers most
    assert prompts.outline_problems([(0, "a"), (1800, "b")], 3600, 4)  # too few
    assert not prompts.outline_problems([(0, "a"), (900, "b"), (1800, "c"), (2700, "d")], 3600, 4)


def test_parse_chapter_normalizes_bullets():
    sec = prompts.parse_chapter("**THEME:** Core idea.\n* **00:04:09** first\n- [00:05:10] second\n")
    assert sec == {"theme": "Core idea.", "bullets": ["[00:04:09] first", "[00:05:10] second"]}
    assert prompts.parse_chapter("THEME: x\n- only one") is None


def test_assembled_brief_validates():
    overview = prompts.split_overview(
        "## Executive Summary\nS.\n## Speaker & Guests\n- A\n## Key Takeaways\n- **K**: v")
    secs = [prompts.render_section(i, {"title": f"T{i}", "theme": "t", "bullets": [f"[00:0{i}:00] a", f"[00:0{i}:30] b"]})
            for i in range(1, 4)]
    brief = prompts.assemble_brief(overview, secs)
    ok, missing = prompts.validate_summary_structure(brief)
    assert ok, missing
    assert brief.index("Speaker & Guests") < brief.index("Thematic Breakdown") < brief.index("Key Takeaways")

