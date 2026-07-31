from __future__ import annotations

import json
from pathlib import Path

from home_finder import web_app_v8
from home_finder.result_store import write_result_records


def result_record(external_id: str = "favorite-1") -> dict:
    return {
        "listing": {
            "source": "591中古屋",
            "external_id": external_id,
            "title": "值得追蹤的三房平車",
            "url": f"https://example.com/{external_id}",
            "city": "高雄市",
            "district": "楠梓區",
            "total_price_wan": 1088,
            "deal_kind": "中古屋",
            "property_type": "電梯大樓",
            "main_area_ping": 18,
            "rooms": 3,
            "baths": 2,
            "parking_type": "平面式",
            "current_floor": 12,
            "total_floors": 15,
            "age_years": 10,
            "search_profile": "大樓公寓華廈",
            "first_seen_at": "2026-07-24T08:00:00+00:00",
            "last_seen_at": "2026-07-24T09:00:00+00:00",
            "lifecycle_status": "seen",
        },
        "profile": "大樓公寓華廈",
        "status": "qualified",
        "score": 90,
        "hard_failures": [],
        "missing_required": [],
        "strengths": ["平面車位"],
        "concerns": [],
        "duplicate_ids": [],
    }


def test_favorite_persists_after_listing_leaves_current_results(tmp_path, monkeypatch):
    results_path = tmp_path / "current-results.json"
    favorites_path = tmp_path / "favorites.json"
    write_result_records(results_path, [result_record()])
    monkeypatch.setattr(web_app_v8.base, "RESULTS_PATH", results_path)
    monkeypatch.setattr(web_app_v8, "FAVORITES_PATH", favorites_path)
    monkeypatch.setattr(
        web_app_v8.base,
        "_iso_now",
        lambda: "2026-07-24T10:00:00+00:00",
    )

    client = web_app_v8.app.test_client()
    added = client.post(
        "/api/favorites",
        json={"source": "591中古屋", "id": "favorite-1", "action": "add"},
    )

    assert added.status_code == 200
    favorite = added.get_json()["favorites"][0]
    assert favorite["title"] == "值得追蹤的三房平車"
    assert favorite["favorite_saved_at"] == "2026-07-24T10:00:00+00:00"
    assert favorite["favorite_is_current"] is True
    assert added.get_json()["summary"]["favorites"] == 1

    saved = json.loads(favorites_path.read_text(encoding="utf-8"))
    assert saved["version"] == 2
    current_card = added.get_json()["groups"]["exact_match"][0]
    assert current_card["is_favorite"] is True
    assert current_card["favorite_is_current"] is True
    assert current_card["favorite_saved_at"] == "2026-07-24T10:00:00+00:00"

    assert saved["items"][0]["source"] == "591中古屋"

    write_result_records(results_path, [])
    historical = web_app_v8.load_dashboard_payload()

    assert historical["summary"]["favorites"] == 1
    assert historical["favorites"][0]["id"] == "favorite-1"
    assert historical["favorites"][0]["favorite_is_current"] is False
    assert historical["favorites"][0]["favorite_last_seen_at"] == "2026-07-24T09:00:00+00:00"

    removed = client.post(
        "/api/favorites",
        json={"source": "591中古屋", "id": "favorite-1", "action": "remove"},
    )
    assert removed.status_code == 200
    assert removed.get_json()["favorites"] == []
    assert json.loads(favorites_path.read_text(encoding="utf-8"))["items"] == []


def test_favorite_keeps_price_and_parking_change_history(tmp_path, monkeypatch):
    results_path = tmp_path / "current-results.json"
    favorites_path = tmp_path / "favorites.json"
    write_result_records(results_path, [result_record()])
    monkeypatch.setattr(web_app_v8.base, "RESULTS_PATH", results_path)
    monkeypatch.setattr(web_app_v8, "FAVORITES_PATH", favorites_path)
    monkeypatch.setattr(
        web_app_v8.base,
        "_iso_now",
        lambda: "2026-07-24T10:00:00+00:00",
    )
    client = web_app_v8.app.test_client()
    added = client.post(
        "/api/favorites",
        json={"source": "591中古屋", "id": "favorite-1", "action": "add"},
    )
    assert added.status_code == 200

    changed = result_record()
    changed["listing"]["total_price_wan"] = 998
    changed["listing"]["parking_type"] = "機械式"
    changed["listing"]["last_seen_at"] = "2026-07-24T11:00:00+00:00"
    write_result_records(results_path, [changed])

    payload = web_app_v8.load_dashboard_payload()
    favorite = payload["favorites"][0]
    assert favorite["favorite_changes"] == [
        "總價：1088 萬 → 998 萬",
        "車位：平面式 → 機械式",
    ]
    assert favorite["favorite_change_detected_at"] == "2026-07-24T10:00:00+00:00"

    saved = json.loads(favorites_path.read_text(encoding="utf-8"))
    assert saved["items"][0]["price"] == 998
    assert len(saved["items"][0]["change_history"]) == 1

    payload_again = web_app_v8.load_dashboard_payload()
    assert len(payload_again["favorites"][0]["favorite_change_history"]) == 1
    saved_again = json.loads(favorites_path.read_text(encoding="utf-8"))
    assert len(saved_again["items"][0]["change_history"]) == 1

    changed_again = result_record()
    changed_again["listing"]["total_price_wan"] = 980
    changed_again["listing"]["parking_type"] = "機械式"
    changed_again["listing"]["last_seen_at"] = "2026-07-24T12:00:00+00:00"
    write_result_records(results_path, [changed_again])

    second_change = web_app_v8.load_dashboard_payload()["favorites"][0]
    assert second_change["favorite_changes"] == ["總價：998 萬 → 980 萬"]
    assert len(second_change["favorite_change_history"]) == 2
    saved_second = json.loads(favorites_path.read_text(encoding="utf-8"))
    assert len(saved_second["items"][0]["change_history"]) == 2


def test_favorite_api_rejects_unknown_listing(tmp_path, monkeypatch):
    results_path = tmp_path / "current-results.json"
    write_result_records(results_path, [])
    monkeypatch.setattr(web_app_v8.base, "RESULTS_PATH", results_path)
    monkeypatch.setattr(web_app_v8, "FAVORITES_PATH", tmp_path / "favorites.json")

    response = web_app_v8.app.test_client().post(
        "/api/favorites",
        json={"source": "591中古屋", "id": "missing", "action": "add"},
    )

    assert response.status_code == 404
    assert response.is_json


def test_damaged_favorite_file_is_not_overwritten(tmp_path, monkeypatch):
    results_path = tmp_path / "current-results.json"
    favorites_path = tmp_path / "favorites.json"
    write_result_records(results_path, [result_record()])
    favorites_path.write_text("{damaged", encoding="utf-8")
    monkeypatch.setattr(web_app_v8.base, "RESULTS_PATH", results_path)
    monkeypatch.setattr(web_app_v8, "FAVORITES_PATH", favorites_path)

    response = web_app_v8.app.test_client().post(
        "/api/favorites",
        json={"source": "591中古屋", "id": "favorite-1", "action": "add"},
    )

    assert response.status_code == 500
    assert response.is_json
    assert "已停止寫入" in response.get_json()["error"]
    assert favorites_path.read_text(encoding="utf-8") == "{damaged"


def test_v8_page_and_assets_expose_favorite_controls():
    with web_app_v8.app.test_request_context("/"):
        page = web_app_v8.index_v8()
    static_dir = Path(web_app_v8.__file__).with_name("static")
    script = (static_dir / "dashboard_v8.js").read_text(encoding="utf-8")

    assert "/static/dashboard_v8.css" in page
    assert "/static/dashboard_v8.js" in page
    assert "我的收藏" in script
    assert "favorite-toggle" in script
    assert 'fetch("/api/favorites"' in script
    assert "favorite_saved_at" in script
    assert "favorite_changes" in script
    assert "收藏後最近變動" in script
    assert "查看全部" in script
