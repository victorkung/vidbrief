import pytest

from vidbrief import voices
from vidbrief.config import load_settings


def test_catalog_has_english_voices_with_recommended_first():
    cat = voices.catalog()
    assert len(cat) == 28
    assert cat[0]["id"] == voices.DEFAULT_VOICE and cat[0]["name"] == "Heart"
    assert {v["accent"] for v in cat} == {"American", "British"}


def test_lang_code_follows_accent():
    assert voices.lang_code("af_heart") == "a"
    assert voices.lang_code("bm_george") == "b"


def test_saved_voice_round_trip_and_overrides_env(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("TTS_VOICE", "am_adam")
    assert load_settings().tts_voice == "am_adam"
    voices.save_voice(tmp_path, "bf_emma")
    assert voices.saved_voice(tmp_path) == "bf_emma"
    assert load_settings().tts_voice == "bf_emma"


def test_unknown_voice_rejected(tmp_path):
    with pytest.raises(ValueError):
        voices.save_voice(tmp_path, "xx_nope")
    (tmp_path / "settings.json").write_text('{"tts_voice": "xx_nope"}')
    assert voices.saved_voice(tmp_path) is None


def test_preview_is_a_personal_intro_and_cache_tracks_wording(monkeypatch):
    assert voices.preview_text("bm_george") == "Hi, I'm George. I will read your briefs like this."
    before = voices.preview_filename("bm_george")
    assert before.startswith("bm_george-") and before.endswith(".mp3")
    monkeypatch.setattr(voices, "PREVIEW_TEMPLATE", "Hello, {name} here.")
    assert voices.preview_filename("bm_george") != before
