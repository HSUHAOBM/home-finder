from __future__ import annotations

import copy

from home_finder import web_app as base
from home_finder import web_app_v5
from home_finder.user_models import HomeListing
from home_finder.user_ranking_v6 import evaluate_all, evaluate_listing


def listing(external_id: str = "A", **changes) -> HomeListing:
    values = dict(
        source="591中古屋",
        external_id=external_id,
        title=f"測試房源 {external_id}",
        url=f"https://example.com/{external_id}",
        city="高雄市",
        district="楠梓區",
        total_price_wan=1050,
        deal_kind="中古屋",
        property_type="電梯大樓",
        main_area_ping=18,
        rooms=2,
        baths=2,
        age_years=5,
        current_floor=9,
        total_floors=15,
        parking_type="平面式",
        has_parking=True,
        search_profile="大樓公寓華廈",
    )
    values.update(changes)
    return HomeListing(**values)


def test_floor_two_thirds_is_preference_by_default():
    settings = copy.deepcopy(web_app_v5.DEFAULT_SETTINGS)
    result = evaluate_listing(listing(), "大樓公寓華廈", settings)

    assert settings["profiles"]["大樓公寓華廈"]["require_high_floor"] is False
    assert result.status == "qualified"
    assert any("未達偏好樓層 10 樓" in concern for concern in result.concerns)


def test_floor_can_still_be_made_a_hard_requirement():
    settings = copy.deepcopy(web_app_v5.DEFAULT_SETTINGS)
    settings["profiles"]["大樓公寓華廈"]["require_high_floor"] = True
    result = evaluate_listing(listing(), "大樓公寓華廈", settings)

    assert result.status == "rejected"
    assert any("低於最低 10 樓" in failure for failure in result.hard_failures)


def test_dashboard_exposes_single_failure_as_near_match():
    settings = copy.deepcopy(web_app_v5.DEFAULT_SETTINGS)
    records = [
        item.to_dict()
        for item in evaluate_all([listing(main_area_ping=14)], settings)
    ]
    payload = web_app_v5.build_dashboard_payload(records)

    assert payload["profile_insights"]["大樓公寓華廈"]["qualified"] == 0
    assert payload["profile_insights"]["大樓公寓華廈"]["near_match"] == 1
    assert payload["groups"]["near_match"][0]["id"] == "A"


def test_merging_one_goal_preserves_the_other_two():
    existing = [
        listing("old-condo"),
        listing(
            "house",
            property_type="透天厝",
            search_profile="透天別墅",
        ),
        listing(
            "presale",
            source="591預售屋",
            deal_kind="預售屋",
            property_type=None,
            search_profile="預售屋",
        ),
    ]
    merged = web_app_v5.merge_target_listings(
        existing, [listing("new-condo")], "大樓公寓華廈"
    )

    assert {item.external_id for item in merged} == {"new-condo", "house", "presale"}


def test_search_api_requires_and_forwards_one_profile(monkeypatch):
    captured = {}

    class FakeThread:
        def __init__(self, target, args, daemon):
            captured.update(target=target, args=args, daemon=daemon)

        def start(self):
            captured["started"] = True

    monkeypatch.setattr(web_app_v5.threading, "Thread", FakeThread)
    with base._state_lock:
        base._state["running"] = False

    client = web_app_v5.app.test_client()
    assert client.post("/api/search", json={}).status_code == 400
    response = client.post("/api/search", json={"profile": "透天別墅"})

    assert response.status_code == 202
    assert captured["args"] == ("透天別墅", "daily")
    assert captured["daemon"] is True
    assert captured["started"] is True
    with base._state_lock:
        base._state["running"] = False


def test_crawler_is_always_headless(monkeypatch):
    captured = {}

    class FakeCrawler:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def fetch(self):
            return []

    monkeypatch.setattr(web_app_v5, "MultiPage591ResaleCrawler", FakeCrawler)
    web_app_v5._crawl_profile(
        "大樓公寓華廈",
        copy.deepcopy(web_app_v5.DEFAULT_SETTINGS),
        {"delay_seconds": 2, "headless": False},
    )

    assert captured["headless"] is True
    assert captured["profile"] == "大樓公寓華廈"


def test_v5_page_loads_per_goal_controls():
    page = web_app_v5.app.test_client().get("/").get_data(as_text=True)

    assert "dashboard_v5.js" in page
    assert "dashboard_v5.css" in page
