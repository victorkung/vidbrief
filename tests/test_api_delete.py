from pathlib import Path

from vidbrief import api


def test_folder_inside_briefs_is_deletable(tmp_path, monkeypatch):
    monkeypatch.setattr(api.settings, "briefs_dir", tmp_path)
    inside = tmp_path / "2026-10-01 Show"
    inside.mkdir()
    assert api._folder_to_delete({"folder": str(inside)}) == inside.resolve()


def test_folder_outside_briefs_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(api.settings, "briefs_dir", tmp_path / "briefs")
    (tmp_path / "briefs").mkdir()
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    assert api._folder_to_delete({"folder": str(outside)}) is None
    assert api._folder_to_delete({"folder": str(tmp_path / "briefs")}) is None
    assert api._folder_to_delete({"folder": str(tmp_path / "briefs" / ".." / "elsewhere")}) is None
    assert api._folder_to_delete({}) is None
