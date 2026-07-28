from __future__ import annotations

import copy

from home_finder import web_app as base
from home_finder import web_app_v6
from home_finder.web_app_v4 import DEFAULT_SETTINGS
from home_finder.user_models import HomeListing
from home_finder.user_ranking_v6 import evaluate_all


def listing(external_id: str = "A", **changes) -> HomeListing:
    values = dict(
        source="591中古屋",
        external_id=external_id,
        title=f"測試房源 {external_id}",
        url=f"https://example.com/{external_id}",
        city="高雄市",
        district="橋頭區",
        total_price_wan=1100,
        deal_kind="中古屋",
        property_type="電梯大樓",
        main_area_ping=18,
        rooms=2,
        baths=2,
        age_years=5,
        current_floor=10,
        total_floors=15,
        community="同一社區",
        address="同一條路 1 號",
        parking_type="平面式",
        has_parking=True,
        search_profile="大樓公寓華廈",
    )
    values.update(changes)
    return HomeListing(**values)


def payload_for(listings: list[HomeListing]) -> dict:
    settings = copy.deepcopy(DEFAULT_SETTINGS)
    settings["profiles"]["大樓公寓華廈"]["require_high_floor"] = False
    records = [item.to_dict() for item in evaluate_all(listings, settings)]
    return web_app_v6.build_dashboard_payload(records)


def test_exact_match_requires_ideal_price_baths_age_and_floor():
    payload = payload_for([listing()])

    assert payload["summary"]["exact_match"] == 1
    assert payload["summary"]["acceptable"] == 0


def test_hard_match_with_lower_floor_is_only_acceptable():
    payload = payload_for([listing(current_floor=9)])

    assert payload["summary"]["exact_match"] == 0
    assert payload["summary"]["acceptable"] == 1
    assert "樓層未達全棟 2/3" in payload["groups"]["acceptable"][0]["ideal_gaps"][0]


def test_similar_ads_are_grouped_as_one_property():
    payload = payload_for(
        [
            listing("A", main_area_ping=22.41, total_price_wan=1198, current_floor=13, total_floors=22),
            listing("B", main_area_ping=22.42, total_price_wan=1198, current_floor=13, total_floors=22),
            listing("C", main_area_ping=22.41, total_price_wan=1198, current_floor=13, total_floors=22),
        ]
    )

    assert payload["summary"]["source_listings"] == 3
    assert payload["summary"]["total"] == 1
    assert payload["summary"]["acceptable"] == 1
    assert len(payload["groups"]["acceptable"][0]["variants"]) == 3


def test_daily_merge_keeps_old_target_while_full_replaces_it():
    old = listing("old")
    other = listing(
        "house",
        property_type="透天厝",
        search_profile="透天別墅",
    )
    new = listing("new")

    daily = web_app_v6.merge_search_results(
        [old, other], [new], "大樓公寓華廈", "daily"
    )
    full = web_app_v6.merge_search_results(
        [old, other], [new], "大樓公寓華廈", "full"
    )

    assert {item.external_id for item in daily} == {"old", "house", "new"}
    assert {item.external_id for item in full} == {"house", "new"}


def test_full_mode_uses_ten_pages_and_thirty_days(monkeypatch):
    captured = {}

    def fake_crawl(profile, settings, source):
        captured.update(
            profile=profile,
            pages=settings["search"]["pages"],
            publish_days=settings["search"]["publish_days"],
        )
        return []

    monkeypatch.setattr(web_app_v6.previous, "_crawl_profile", fake_crawl)
    web_app_v6._crawl_for_mode(
        "大樓公寓華廈",
        copy.deepcopy(web_app_v6.load_settings()),
        {},
        "full",
    )

    assert captured == {
        "profile": "大樓公寓華廈",
        "pages": 10,
        "publish_days": 30,
    }


def test_search_api_forwards_profile_and_mode(monkeypatch):
    captured = {}

    class FakeThread:
        def __init__(self, target, args, daemon):
            captured.update(target=target, args=args, daemon=daemon)

        def start(self):
            captured["started"] = True

    monkeypatch.setattr(web_app_v6.threading, "Thread", FakeThread)
    with base._state_lock:
        base._state["running"] = False

    client = web_app_v6.app.test_client()
    response = client.post(
        "/api/search", json={"profile": "大樓公寓華廈", "mode": "full"}
    )

    assert response.status_code == 202
    assert captured["args"] == ("大樓公寓華廈", "full")
    assert captured["daemon"] is True
    assert captured["started"] is True
    with base._state_lock:
        base._state["running"] = False


def test_v6_page_loads_goal_finding_controls():
    page = web_app_v6.app.test_client().get("/").get_data(as_text=True)

    assert "dashboard_v6.js" in page
    assert "dashboard_v6.css" in page
