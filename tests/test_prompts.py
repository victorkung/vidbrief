from vidbrief import prompts

COMPLETE = """## Executive Summary
Hello.

## Speaker & Guests
- A

## Thematic Breakdown
### Section 1: One
### Section 2: Two
### Section 3: Three

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
