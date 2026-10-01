from vidbrief import chunking


def segs(n, every=10.0, text="word " * 20):
    return [{"start": i * every, "text": text} for i in range(n)]


def test_format_hms():
    assert chunking.format_hms(0) == "00:00:00"
    assert chunking.format_hms(3725.9) == "01:02:05"


def test_paragraphs_group_by_minute():
    paras = chunking.paragraphs(segs(13))  # 0..120s
    assert [round(t) for t, _ in paras] == [0, 60, 120]


def test_render_labels():
    out = chunking.render([(0, "a"), (61, "b")])
    assert out == "00:00:00\na\n\n00:01:01\nb"


def test_single_window_when_short():
    paras = chunking.paragraphs(segs(30))
    assert len(chunking.windows(paras, max_tokens=100_000)) == 1


def test_windows_split_with_overlap_and_cover_all():
    paras = chunking.paragraphs(segs(600))  # ~100 minutes
    wins = chunking.windows(paras, max_tokens=1500, overlap=1)
    assert len(wins) > 1
    for prev, nxt in zip(wins, wins[1:]):
        assert nxt[0] == prev[-1]  # one paragraph of overlap
    seen = {t for w in wins for t, _ in w}
    assert seen == {t for t, _ in paras}


def test_empty():
    assert chunking.windows([], max_tokens=10) == []
