from __future__ import annotations

import copy

from home_finder.crawler_591_browser import (
    DETAIL_CACHE_PATH,
    Browser591Crawler,
    parse_detail_text,
)
from home_finder.user_models import HomeListing
from home_finder.user_ranking_v6 import evaluate_listing
from home_finder.web_app_v4 import DEFAULT_SETTINGS


def listing() -> HomeListing:
    return HomeListing(
        source="591中古屋",
        external_id="20599456",
        title="誠售｜大社綠波庭｜次高樓層採光通風3房車位",
        url="https://sale.591.com.tw/home/house/detail/2/20599456.html",
        city="高雄市",
        district="大社區",
        total_price_wan=750,
        deal_kind="中古屋",
        property_type="電梯大樓",
        main_area_ping=24.6,
        rooms=3,
        living_rooms=2,
        baths=2,
        age_years=28,
        current_floor=6,
        total_floors=7,
        search_profile="大樓公寓華廈",
    )


def test_description_mechanical_parking_overrides_structured_flat_parking():
    body = """
def test_resale_cache_path_is_versioned_after_parser_change():
    crawler = Browser591Crawler(
        districts=["大社區"],
        max_details=1,
        delay_seconds=2,
        sleep=lambda _seconds: None,
    )

    assert str(crawler.cache_path) == DETAIL_CACHE_PATH


    型態：電梯大樓 裝潢程度：尚未裝潢
    車位：平面式，已含售金內 坪數說明
    主建物：24.6坪
    屋況特色：車道分流，B1機械上層車位
    """

    parsed = parse_detail_text(listing(), body)

    assert parsed.parking_type == "B1機械上層車位"
    assert parsed.has_parking is True
    assert parsed.data_warnings == [
        "車位資料矛盾：房屋資料標示「平面式，已含售金內」，內文寫「B1機械上層車位」"
    ]

    result = evaluate_listing(
        parsed, "大樓公寓華廈", copy.deepcopy(DEFAULT_SETTINGS)
    )
    assert result.status == "rejected"
    assert result.hard_failures == ["不是平面車位：B1機械上層車位"]
