from pathlib import Path

from vidbrief.speech import brief_to_speech

ROOT = Path(__file__).resolve().parents[1]

BRIEF = """*Title · Chan · Published Aug 5, 2026 · 37 min*

## High-Level Overview
Rates rose ~$200M — and fast.

### Chapter 2: Options & Liquidity
Intro sentence

- [00:13:26] **MSTR Selling**: Strategy sold $104M of BTC at 64K over 5–10 days vs. peers.
- **00:27:11** **Warsh Paradigm**: The 30-year yield hit 5.17%, see https://example.com.
- ★ [1:02:03] Plain point with [a link](https://x.com/a)
"""


def test_speech_strips_markup_and_reads_naturally():
    text = brief_to_speech(BRIEF, title="Bitcoin vs. Nasdaq…", uploader="The DeFi Report")
    lines = text.splitlines()
    assert lines[0] == "VidBrief summary of Bitcoin versus Nasdaq, from The DeFi Report."
    assert "High-Level Overview." in lines
    assert "Chapter 2. Options and Liquidity." in lines
    assert "Intro sentence." in lines
    assert "MSTR Selling. Strategy sold $104 million of BTC at 64 thousand over 5 to 10 days versus peers." in lines
    assert "Warsh Paradigm. The 30-year yield hit 5.17%, see." in lines
    assert "Plain point with a link." in lines
    assert "about $200 million, and fast." in text
    for bad in ("*", "#", "★", "[", "http", "00:", "·"):
        assert bad not in text, bad


def test_speech_on_reference_briefs_has_no_markup():
    for path in (ROOT / "docs/reference").glob("podbrief-*.md"):
        text = brief_to_speech(path.read_text())
        for bad in ("*", "#", "[", "00:"):
            assert bad not in text, (path.name, bad)
