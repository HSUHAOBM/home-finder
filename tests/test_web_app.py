from __future__ import annotations

import json

from home_finder import web_app


def _record(external_id: str, profile: str, status: str, score: float = 50) -> dict:
    return {
        "listing": {
            "external_id": external_id,
            "title": f"房源 {external_id}",
            "url": f"https://example.com/{external_id}",
            "district": "楠梓區",
            "deal_kind": "預售屋" if profile == "預售屋" else "中古屋",
            "property_type": "電梯大樓" if profile != "透天別墅" else "透天厝",
            "total_price_wan": 1100,
            "main_area_ping": 18,
            "rooms": 2,
            "baths": 2,
            "parking_type": "平面式",
            "current_floor": 8,
            "total_floors": 12,
            "age_years": 5,
        },
        "profile": profile,
        "status": status,
        "score": score,
        "hard_failures": [],
        "missing_required": [],
        "strengths": [],
        "concerns": [],
        "duplicate_ids": [],
    }


def test_selects_one_matching_profile_per_listing():
    records = [
        _record("A", "大樓公寓華廈", "qualified", 80),
        _record("A", "透天別墅", "rejected", 20),
        _record("A", "預售屋", "rejected", 20),
        _record("B", "預售屋", "needs_verification", 70),
        _record("B", "大樓公寓華廈", "rejected", 10),
    ]

    selected = web_app.select_listing_results(records)

    assert len(selected) == 2
    assert selected[0]["listing"]["external_id"] == "A"
    assert selected[0]["status"] == "qualified"
    assert selected[1]["listing"]["external_id"] == "B"
    assert selected[1]["profile"] == "預售屋"


def test_results_api_returns_unique_listing_counts(tmp_path, monkeypatch):
    records = [
        _record("A", "大樓公寓華廈", "qualified"),
        _record("A", "透天別墅", "rejected"),
        _record("B", "預售屋", "needs_verification"),
    ]
    results_path = tmp_path / "results.json"
    results_path.write_text(json.dumps(records), encoding="utf-8")
    monkeypatch.setattr(web_app, "RESULTS_PATH", results_path)

    response = web_app.app.test_client().get("/api/results")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["summary"]["total"] == 2
    assert payload["summary"]["qualified"] == 1
    assert payload["summary"]["needs_verification"] == 1
    assert payload["summary"]["rejected"] == 0


def test_homepage_has_search_button():
    response = web_app.app.test_client().get("/")

    assert response.status_code == 200
    assert "開始重新搜尋" in response.get_data(as_text=True)
