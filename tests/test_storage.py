from __future__ import annotations

import json

import pytest

from home_finder import storage


def test_atomic_write_json_replaces_existing_file(tmp_path):
    target = tmp_path / "state.json"
    target.write_text('{"old": true}', encoding="utf-8")

    storage.atomic_write_json(target, {"new": "完成"})

    assert json.loads(target.read_text(encoding="utf-8")) == {"new": "完成"}
    assert list(tmp_path.glob(".state.json.*.tmp")) == []


def test_atomic_write_failure_preserves_existing_file(tmp_path, monkeypatch):
    target = tmp_path / "state.json"
    target.write_text('{"old": true}', encoding="utf-8")

    def fail_replace(source, destination):
        raise OSError("replace failed")

    monkeypatch.setattr(storage.os, "replace", fail_replace)

    with pytest.raises(OSError, match="replace failed"):
        storage.atomic_write_json(target, {"new": True})

    assert json.loads(target.read_text(encoding="utf-8")) == {"old": True}
    assert list(tmp_path.glob(".state.json.*.tmp")) == []
