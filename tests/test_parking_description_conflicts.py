from __future__ import annotations

import copy

from home_finder.crawler_591_browser import (
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
    型態：電梯大樓 裝潢程度：尚未裝潢
    車位：平面式，已含售金內 坪數說明
    主建物：24.6坪
    屋況特色：車道分流，B1機械上層車位
    買房知識
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


def test_recommendations_do_not_override_structured_flat_parking_or_garden():
    body = """
    型態：電梯大樓 裝潢程度：尚未裝潢
    車位：6.522坪，平面式，已含售金內 坪數說明
    主建物：24.6坪
    屋況特色：格局方正，前後大陽台採光佳
    買房知識
    附近搶手物件推薦
    兩房機械車位
    王子大花園
    """

    parsed = parse_detail_text(listing(), body)

    assert parsed.parking_type == "6.522坪，平面式，已含售金內"
    assert parsed.has_parking is True
    assert parsed.has_garden is None
    assert parsed.data_warnings == []


def test_other_structured_parking_value_is_treated_as_existing_parking():
    body = """
    型態：電梯大樓 裝潢程度：尚未裝潢
    車位：坡道固定車位 坪數說明
    屋況特色：格局方正
    買房知識
    """

    parsed = parse_detail_text(listing(), body)

    assert parsed.parking_type == "坡道固定車位"
    assert parsed.has_parking is True


def test_flat_parking_comparison_does_not_assert_mechanical_parking():
    body = """
    車位：4.171坪，平面式，已含售金內 公設比：33% 坪數說明
    主建物：13.56坪
    屋況特色：⑤ 平面車位，不用每天跟機械車位搏鬥 🚗
    B3地下室平面車位，採坡道式進出。 買房知識
    """
    parsed = parse_detail_text(listing(), body)
    assert parsed.parking_type == "4.171坪，平面式，已含售金內"
    assert parsed.has_parking is True
    assert parsed.data_warnings == []
    for phrase in ("不是機械車位", "無機械車位困擾", "沒有機械車位"):
        parsed = parse_detail_text(listing(), f"車位：平面式 坪數說明 屋況特色：{phrase} 買房知識")
        assert parsed.parking_type == "平面式"
        assert parsed.data_warnings == []


def test_structured_parking_without_area_section():
    parsed = parse_detail_text(listing(), "車位\n：\n平面式，已含售金內\n屋況特色\n景觀佳\n買房知識")
    assert parsed.parking_type == "平面式，已含售金內"
    assert parsed.has_parking is True


def test_positive_mechanical_description_is_not_negated_by_very():
    parsed = parse_detail_text(listing(), "車位：平面式 坪數說明 屋況特色：非常方便的B1機械車位 買房知識")
    assert parsed.parking_type == "B1機械車位"
    assert parsed.data_warnings


def test_feature_parking_field_is_used_without_structured_parking():
    parsed = parse_detail_text(listing(), "屋況特色：✅️車位：平面車位（B2-68） 買房知識 機械車位推薦")
    assert parsed.parking_type == "平面車位（屋況特色）"
    assert parsed.has_parking is True


def test_nearby_rental_parking_is_not_owned_parking():
    parsed = parse_detail_text(listing(), "屋況特色：附近可租平面車位 買房知識")
    assert parsed.parking_type is None
    assert parsed.has_parking is None


def test_structured_flat_parking_shorthand_is_normalized():
    for raw, expected in (("平車，已含售金內", "平面車位，已含售金內"),
                          ("坡平，已含售金內", "坡道平面，已含售金內")):
        parsed = parse_detail_text(listing(), f"車位：{raw} 坪數說明")
        assert parsed.parking_type == expected
        result = evaluate_listing(parsed, "大樓公寓華廈", copy.deepcopy(DEFAULT_SETTINGS))
        assert not any("不是平面車位" in failure for failure in result.hard_failures)


def test_mixed_flat_and_mechanical_label_is_not_accepted_as_flat_parking():
    body = """
    型態：電梯大樓 裝潢程度：尚未裝潢
    車位：2.314坪，平面式+機械式，已含售金內 坪數說明
    主建物：24.6坪
    屋況特色：平移車位可停休旅
    買房知識
    """

    parsed = parse_detail_text(listing(), body)
    result = evaluate_listing(
        parsed, "大樓公寓華廈", copy.deepcopy(DEFAULT_SETTINGS)
    )

    assert parsed.parking_type == "2.314坪，平面式+機械式，已含售金內"
    assert result.status == "rejected"
    assert result.hard_failures == [
        "不是平面車位：2.314坪，平面式+機械式，已含售金內"
    ]


def test_sliding_parking_label_is_not_accepted_as_flat_parking():
    candidate = listing()
    candidate.parking_type = "平移車位"
    candidate.has_parking = True

    result = evaluate_listing(
        candidate, "大樓公寓華廈", copy.deepcopy(DEFAULT_SETTINGS)
    )

    assert result.status == "rejected"
    assert result.hard_failures == ["不是平面車位：平移車位"]


def test_resale_cache_path_is_versioned_after_parser_change():
    crawler = Browser591Crawler(
        districts=["大社區"],
        max_details=1,
        delay_seconds=2,
        sleep=lambda _seconds: None,
    )

    assert crawler.cache_path.as_posix() == "data/cache/591_details_v7.json"


def test_detail_reads_age_in_months_from_summary():
    parsed = parse_detail_text(
        listing(),
        "格局 3房2廳2衛1陽台 8個月 屋齡 28.5坪 權狀坪數 房屋介紹",
    )

    assert parsed.age_years == 0.67
