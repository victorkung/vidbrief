from vidbrief import prompts

COMPLETE = """## High-Level Overview
Hello.

## Context
Who.

### Chapter 1: One
- [00:00:10] a
### Chapter 2: Two
- [00:10:00] b
### Chapter 3: Three
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
    assert "High-Level Overview" in missing


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
    body = "\n".join(f"### Chapter {i}: T\n- [00:0{i % 10}:00] a\n- [00:0{i % 10}:30] b" for i in range(1, 15))
    text = f"## High-Level Overview\nx\n{body}\n## Key Takeaways\n- y\n"
    ok, missing = prompts.validate_summary_structure(text)
    assert not ok
    assert any("at most" in m for m in missing)


def test_section_count_grows_slowly():
    assert prompts.section_count(18 * 60) == 3
    assert prompts.section_count(60 * 60) == 4
    assert prompts.section_count(90 * 60) == 5
    assert prompts.section_count(150 * 60) == 7
    assert prompts.section_count(5 * 3600) == 8


def test_target_words_sublinear_and_capped():
    assert prompts.target_words(30 * 60) == 485
    assert prompts.target_words(3600) == 650
    assert prompts.target_words(150 * 60) == 1145
    assert prompts.target_words(5 * 3600) == 1250


def test_parse_points_accepts_timestamp_styles():
    text = "[00:01:00] one\n**00:02:30** two\n- [1:03:05] three\nnot a point\n★ [00:04:00] big\n- [00:05:00] ★ also"
    assert prompts.parse_points(text) == [(60, "one", False), (150, "two", False), (3785, "three", False),
                                          (240, "big", True), (300, "also", True)]


def test_points_round_trip_with_stars():
    pts = [(0, "intro", False), (75, "advice", True)]
    assert prompts.parse_points(prompts.render_points(pts, bullets=True)) == pts


def test_key_points_grouped_by_chapter():
    pts = [(0, "a", False), (70, "b", True), (200, "c", False)]
    md = prompts.key_points_md(pts, [(0, "First"), (120, "Second")], 300)
    assert md.index("### Chapter 1: First") < md.index("- ★ [00:01:10] b") < md.index("### Chapter 2: Second")
    assert "- [00:03:20] c" in md


def test_priorities_injected_into_prompts():
    text = prompts.load_prompt("chapter")
    assert "{priorities}" not in text
    assert "Actionable advice" in text


def test_trim_drops_unimportant_bullets_first():
    secs = [{"title": "T", "intro": "i", "bullets": [
        "[00:00:10] **A**: important point here", "[00:00:20] **B**: filler " + "word " * 20,
        "[00:00:30] **C**: also key", "[00:00:40] **D**: extra"]}]
    out = prompts.trim_sections(secs, budget=17, fixed_words=0, key_ts={10, 30})
    kept = out[0]["bullets"]
    assert any("**A**" in b for b in kept) and any("**C**" in b for b in kept)
    assert len(kept) == 2
    assert len(secs[0]["bullets"]) == 4  # input untouched


def test_parse_outline_sorts_dedupes_and_starts_at_zero():
    text = "[00:00:05] Intro Topic\n[00:30:00] Later\n[00:12:00] Middle\n[00:12:00] Dup\n[02:00:00] Past end"
    assert prompts.parse_outline(text, 3600) == [(0, "Intro Topic"), (720, "Middle"), (1800, "Later")]


def test_outline_problems_flags_imbalance_and_count():
    assert prompts.outline_problems([(0, "a"), (60, "b"), (120, "c")], 3600, 4)  # last covers most
    assert prompts.outline_problems([(0, "a"), (1800, "b")], 3600, 4)  # too few
    assert not prompts.outline_problems([(0, "a"), (900, "b"), (1800, "c"), (2700, "d")], 3600, 4)


def test_parse_chapter_normalizes_bullets():
    sec = prompts.parse_chapter("**INTRO:** Core idea.\nSecond line.\n* **00:04:09** **Label**: first\n- [00:05:10] second\n")
    assert sec == {"intro": "Core idea. Second line.", "bullets": ["[00:04:09] **Label**: first", "[00:05:10] second"]}
    assert prompts.parse_chapter("INTRO: x\n- only one") is None


def test_assembled_brief_validates():
    overview = prompts.split_overview(
        "## High-Level Overview\nS.\n## Context\nWho.\n## Key Takeaways\n- **K**: v")
    secs = [prompts.render_section(i, {"title": f"T{i}", "intro": "t", "bullets": [f"[00:0{i}:00] a", f"[00:0{i}:30] b"]})
            for i in range(1, 4)]
    brief = prompts.assemble_brief(overview, secs, "*Title · Channel · Published Aug 5, 2026*")
    ok, missing = prompts.validate_summary_structure(brief)
    assert ok, missing
    assert brief.startswith("*Title")
    assert brief.index("## Context") < brief.index("### Chapter 1") < brief.index("## Key Takeaways")



def test_merge_short_chapters_folds_cold_open_forward():
    starts = [(0, "Teaser"), (60, "Also Teaser"), (124, "Longevity"), (1500, "Money"), (2400, "Bitcoin"), (3500, "Allergies")]
    merged = prompts.merge_short_chapters(starts, 4020, 5)
    assert merged[0] == (0, "Longevity")
    assert [t for t, _ in merged] == [0, 1500, 2400, 3500]


def test_merge_short_chapters_keeps_minimum_three():
    starts = [(0, "A"), (30, "B"), (60, "C")]
    assert prompts.merge_short_chapters(starts, 3600, 4) == starts


def test_copied_takeaways_detected():
    secs = ["### Chapter 1: T\nIntro\n\n- [00:01:00] **Deep Modules**: Structure code with few large modules and simple interfaces."]
    copied = "- **Deep Modules**: Structure code with few large modules and simple interfaces."
    fresh = "- **Design First**: Spend your time on architecture and let AI handle implementation details."
    assert prompts.copied_takeaways(copied, secs) == 1
    assert prompts.copied_takeaways(fresh, secs) == 0
