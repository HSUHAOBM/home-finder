from __future__ import annotations

import json
from pathlib import Path

from home_finder import web_app_v8, web_app_v12
from home_finder.favorite_availability import (
    AvailabilityResult,
    classify_availability,
)


def favorite(external_id: str, *, profile: str = "大樓公寓華廈") -> dict:
    return {
        "id": external_id,
        "source": "591中古屋",
        "profile": profile,
        "title": f"收藏 {external_id}",
        "url": f"https://sale.591.com.tw/home/house/detail/2/{external_id}.html",
        "saved_at": "2026-08-10T00:00:00+00:00",
    }


class FakeChecker:
    def __init__(self, results: dict[str, AvailabilityResult]):
        self.results = results
        self.checked: list[str] = []

    def check_many(self, favorites, *, on_result):
        for item in favorites:
            self.checked.append(item["id"])
            on_result(item, self.results[item["id"]])


def test_availability_classifier_is_conservative():
    assert classify_availability(
        http_status=404, body="", final_url="https://example.test"
    ).status == "removed"
    assert classify_availability(
        http_status=200, body="此物件已下架", final_url="https://example.test"
    ).status == "removed"
    assert classify_availability(
        http_status=403, body="Cloudflare", final_url="https://example.test"
    ).status == "unknown"
    assert classify_availability(
        http_status=200, body="正常房源內容", final_url="https://example.test"
    ).status == "available"


def test_audit_skips_current_and_other_profile_favorites(tmp_path: Path, monkeypatch):
    favorites_path = tmp_path / "favorites.json"
    favorites_path.write_text(
        json.dumps({"version": 2, "items": [
            favorite("current"),
            favorite("removed"),
            favorite("house", profile="透天厝"),
        ]}, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(web_app_v8, "FAVORITES_PATH", favorites_path)
    checker = FakeChecker({
        "removed": AvailabilityResult("removed", "網址回傳 HTTP 404")
    })

    counts = web_app_v12.audit_favorite_availability(
        {web_app_v8._favorite_key("591中古屋", "current")},
        profile="大樓公寓華廈",
        checker=checker,
        checked_at="2026-08-10T01:00:00+00:00",
    )

    assert checker.checked == ["removed"]
    assert counts == {
        "available": 1,
        "removed": 1,
        "unknown": 0,
        "current": 1,
        "url_checks": 1,
    }
    saved = json.loads(favorites_path.read_text(encoding="utf-8"))["items"]
    assert saved[0]["availability_reason"] == "本次爬蟲已找到"
    assert saved[1]["availability_status"] == "removed"
    assert "availability_status" not in saved[2]


def test_v12_assets_remain_available_for_compatibility():
    with web_app_v12.app.test_request_context("/"):
        page = web_app_v12.index_v12()
    root = Path(web_app_v12.__file__).parents[2]
    assert "/static/dashboard_v12.css" in page
    assert "/static/dashboard_v12.js" in page


def test_availability_survives_current_result_snapshot_refresh(tmp_path, monkeypatch):
    favorites_path = tmp_path / "favorites.json"
    stored = favorite("still-current")
    stored.update({
        "availability_status": "available",
        "availability_checked_at": "2026-08-10T01:00:00+00:00",
        "availability_reason": "本次爬蟲已找到",
    })
    favorites_path.write_text(
        json.dumps({"version": 2, "items": [stored]}, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(web_app_v8, "FAVORITES_PATH", favorites_path)
    payload = {
        "groups": {
            "exact_match": [{
                "id": "still-current",
                "source": "591中古屋",
                "title": "仍在架上的收藏",
                "last_seen_at": "2026-08-10T01:00:00+00:00",
            }]
        },
        "summary": {},
    }

    decorated = web_app_v8._decorate_with_favorites(payload)

    assert decorated["favorites"][0]["availability_status"] == "available"
    saved = json.loads(favorites_path.read_text(encoding="utf-8"))["items"][0]
    assert saved["availability_reason"] == "本次爬蟲已找到"


def test_v12_ui_has_removed_state_and_remove_action():
    root = Path(web_app_v12.__file__).with_name("static")
    script = (root / "dashboard_v12.js").read_text(encoding="utf-8")
    stylesheet = (root / "dashboard_v12.css").read_text(encoding="utf-8")
    assert "已下架" in script
    assert "查核失敗" in script
    assert "移除收藏" in script
    assert ".availability-removed" in stylesheet
