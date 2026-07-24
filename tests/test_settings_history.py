import copy
import json
from pathlib import Path

from home_finder import web_app_v7
from home_finder.settings_history import (
    load_settings_history,
    record_settings_snapshot,
)


def test_settings_history_keeps_changes_and_skips_consecutive_duplicates(tmp_path):
    path = tmp_path / "settings-history.json"
    first_settings = {"districts": ["楠梓區"], "profiles": {"大樓": {"max": 1200}}}
    second_settings = copy.deepcopy(first_settings)
    second_settings["profiles"]["大樓"]["max"] = 1100

    first = record_settings_snapshot(
        path, first_settings, "2026-07-23T01:00:00+00:00"
    )
    duplicate = record_settings_snapshot(
        path, first_settings, "2026-07-23T02:00:00+00:00"
    )
    second = record_settings_snapshot(
        path, second_settings, "2026-07-23T03:00:00+00:00"
    )

    assert duplicate == first
    assert load_settings_history(path) == [first, second]
    first_settings["districts"].append("三民區")
    assert load_settings_history(path)[0]["settings"]["districts"] == ["楠梓區"]


def test_settings_api_preserves_current_and_new_versions(tmp_path, monkeypatch):
    config_path = tmp_path / "config.user.json"
    history_path = tmp_path / "settings-history.json"
    config_path.write_text(
        web_app_v7.base.CONFIG_PATH.read_text(encoding="utf-8"), encoding="utf-8"
    )
    monkeypatch.setattr(web_app_v7.base, "CONFIG_PATH", config_path)
    monkeypatch.setattr(web_app_v7.base, "RESULTS_PATH", tmp_path / "results.json")
    monkeypatch.setattr(web_app_v7.base, "SUMMARY_PATH", tmp_path / "summary.md")
    monkeypatch.setattr(web_app_v7, "DIAGNOSTICS_PATH", tmp_path / "diagnostics.json")
    monkeypatch.setattr(web_app_v7, "SEARCH_HISTORY_PATH", tmp_path / "search-history.json")
    monkeypatch.setattr(web_app_v7, "SETTINGS_HISTORY_PATH", history_path)

    current = web_app_v7.load_settings()
    changed = copy.deepcopy(current)
    changed["profiles"]["大樓公寓華廈"]["target_price"] = 1050
    original_state = web_app_v7.base._state_snapshot()

    try:
        with web_app_v7.base._state_lock:
            web_app_v7.base._state["running"] = False
        client = web_app_v7.app.test_client()
        response = client.post("/api/settings", json=changed)

        assert response.status_code == 200
        payload = response.get_json()
        assert [entry["settings"] for entry in payload["history"]] == [changed, current]
        assert web_app_v7.load_settings() == changed

        repeated = client.post("/api/settings", json=changed)
        assert repeated.status_code == 200
        assert len(repeated.get_json()["history"]) == 2

        history_response = client.get("/api/settings/history")
        assert history_response.status_code == 200
        assert history_response.get_json()["history"] == payload["history"]
    finally:
        with web_app_v7.base._state_lock:
            web_app_v7.base._state.clear()
            web_app_v7.base._state.update(original_state)


def test_settings_history_ui_is_available():
    root = Path(web_app_v7.__file__).parent
    script = (root / "static" / "dashboard_v3.js").read_text(encoding="utf-8")
    template = (root / "templates" / "dashboard_v3.html").read_text(encoding="utf-8")

    assert 'fetch("/api/settings/history"' in script
    assert "settings-history-load" in script
    assert "沿用過去條件" in template
    assert "載入此版本" in template


def test_invalid_settings_history_is_treated_as_empty(tmp_path):
    path = tmp_path / "settings-history.json"
    path.write_text(json.dumps({"unexpected": True}), encoding="utf-8")

    assert load_settings_history(path) == []
