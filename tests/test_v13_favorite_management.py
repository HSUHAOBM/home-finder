from __future__ import annotations

import json
from pathlib import Path

from home_finder import web_app_v8, web_app_v13


def stored_favorite() -> dict:
    return {
        "id": "note-1",
        "source": "591中古屋",
        "title": "想追蹤的房子",
        "url": "https://sale.591.com.tw/home/house/detail/2/note-1.html",
        "saved_at": "2026-08-10T00:00:00+00:00",
        "availability_status": "removed",
        "availability_checked_at": "2026-08-12T00:00:00+00:00",
        "availability_reason": "網址回傳 HTTP 404",
        "removed_at": "2026-08-12T00:00:00+00:00",
        "availability_history": [{
            "checked_at": "2026-08-12T00:00:00+00:00",
            "from": "available",
            "to": "removed",
            "reason": "網址回傳 HTTP 404",
        }],
    }


def test_note_api_saves_and_clears_note(tmp_path: Path, monkeypatch):
    path = tmp_path / "favorites.json"
    path.write_text(
        json.dumps({"version": 2, "items": [stored_favorite()]}, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(web_app_v8, "FAVORITES_PATH", path)
    monkeypatch.setattr(web_app_v8, "_load_previous_dashboard_payload", lambda: {"groups": {}, "summary": {}})
    client = web_app_v13.app.test_client()

    saved = client.post("/api/favorites/note", json={
        "source": "591中古屋", "id": "note-1", "note": "地點很好，屋況需要整理",
    })
    assert saved.status_code == 200
    item = json.loads(path.read_text(encoding="utf-8"))["items"][0]
    assert item["favorite_note"] == "地點很好，屋況需要整理"
    assert item["removed_at"] == "2026-08-12T00:00:00+00:00"

    cleared = client.post("/api/favorites/note", json={
        "source": "591中古屋", "id": "note-1", "note": "",
    })
    assert cleared.status_code == 200
    item = json.loads(path.read_text(encoding="utf-8"))["items"][0]
    assert "favorite_note" not in item


def test_note_api_validates_length(tmp_path: Path, monkeypatch):
    path = tmp_path / "favorites.json"
    path.write_text(json.dumps({"items": [stored_favorite()]}), encoding="utf-8")
    monkeypatch.setattr(web_app_v8, "FAVORITES_PATH", path)
    response = web_app_v13.app.test_client().post("/api/favorites/note", json={
        "source": "591中古屋", "id": "note-1", "note": "字" * 501,
    })
    assert response.status_code == 400
    assert response.get_json()["error"] == "收藏備註最多 500 字"


def test_v13_assets_launcher_and_ui_features():
    with web_app_v13.app.test_request_context("/"):
        page = web_app_v13.index_v13()
    root = Path(web_app_v13.__file__).parents[2]
    static = Path(web_app_v13.__file__).with_name("static")
    script = (static / "dashboard_v13.js").read_text(encoding="utf-8")
    assert "/static/dashboard_v13.css" in page
    assert "/static/dashboard_v13.js" in page
    assert "data-favorite-status" in script
    assert "favorite-note-save" in script
    assert "下架確認" in script
    assert "home_finder.web_app_v13" in (root / "開啟找房介面.cmd").read_text(encoding="utf-8")
    assert "home_finder.web_app_v13" in (root / "README.md").read_text(encoding="utf-8")
