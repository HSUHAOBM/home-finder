from __future__ import annotations

from home_finder.crawler_rakuya import (
    BrowserRakuyaPilotCrawler,
    parse_rakuya_detail_text,
    parse_rakuya_list_card,
)
from home_finder.rakuya_pilot import compare_with_current, select_detail_candidates
from home_finder.user_models import HomeListing


def test_parse_rakuya_card_uses_discounted_price_and_does_not_trust_parking_claim():
    listing = parse_rakuya_list_card({
        "href": "https://community.rakuya.com.tw/7959/sell/info?ehid=0c559a345574112&from=list_prior_sort",
        "title": "鼎山家樂福大兩房加平車",
        "text": (
            "鼎山家樂福大兩房加平車\n加樂富待售房屋\n三民區\n加樂富\n"
            "電梯大廈\n2房2廳1衛\n16.5年\n3/15樓\n"
            "總建36.9坪\n主建16.5坪\n29.81萬/坪\n1,180萬\n1,100萬\n平面車位"
        ),
    })
    assert listing.source == "樂屋網"
    assert listing.external_id == "0c559a345574112"
    assert listing.total_price_wan == 1100
    assert listing.property_type == "電梯大樓"
    assert listing.community == "加樂富"
    assert listing.main_area_ping == 16.5
    assert listing.rooms == 2
    assert listing.current_floor == 3
    assert listing.has_parking is None
    assert listing.parking_type is None
    assert "尚未讀取詳情確認" in listing.data_warnings[0]


def test_rakuya_url_uses_all_configured_districts_and_page():
    crawler = BrowserRakuyaPilotCrawler(
        districts=["三民區", "橋頭區", "大社區"], max_price=1150, max_pages=3
    )
    url = crawler._list_url(2)
    assert "zipcode=807%2C825%2C815" in url
    assert "price=0~1150" in url
    assert "typecode=R1%2CR2" in url
    assert url.endswith("&page=2")


def test_parse_rakuya_detail_prefers_structured_flat_parking_and_brand():
    listing = parse_rakuya_list_card({
        "href": "https://community.rakuya.com.tw/3142/sell/info?ehid=ABC",
        "title": "紫京城兩房平車",
        "text": (
            "紫京城兩房平車\n三民區\n紫京城\n電梯大廈\n"
            "2房2廳1衛\n20.4年\n14/15樓\n總建33.9坪\n"
            "主建16.22坪\n1,100萬\n平面車位"
        ),
    })
    detail = parse_rakuya_detail_text(
        listing,
        """
高雄市三民區明誠一路
類型
住宅/電梯大廈
主建物
16.22坪
車位
有車位
車位類型
平面式車位
永慶不動產-【加盟】美術願景店
願景君箖不動產有限公司
""",
    )
    assert detail.address == "高雄市三民區明誠一路"
    assert detail.parking_type == "平面式車位"
    assert detail.has_parking is True
    assert detail.origin_source == "永慶不動產-【加盟】美術願景店"
    assert detail.broker_name == "願景君箖不動產有限公司"
    assert detail.data_warnings == []


def test_detail_conflict_uses_mechanical_value_instead_of_flat_title():
    listing = HomeListing(
        source="樂屋網", external_id="R", title="廣告寫平車",
        url="https://example.com", city="高雄市", district="三民區",
        total_price_wan=1000, property_type="電梯大樓",
        data_warnings=["樂屋列表提到「平車」，尚未讀取詳情確認車位型式"],
    )
    detail = parse_rakuya_detail_text(
        listing, "車位\n有車位\n車位類型\n機械式車位"
    )
    assert detail.parking_type == "機械式車位"
    assert "列表宣稱平面車位" in detail.data_warnings[0]


def test_detail_does_not_treat_unrelated_company_as_broker():
    listing = HomeListing(
        source="樂屋網", external_id="R", title="測試",
        url="https://example.com", city="高雄市", district="三民區",
        total_price_wan=1000, property_type="電梯大樓",
    )
    detail = parse_rakuya_detail_text(
        listing, "電動機車充電站大樂股份有限公司"
    )
    assert detail.broker_name is None


def test_rakuya_browser_runs_offscreen_by_default():
    crawler = BrowserRakuyaPilotCrawler(
        districts=["三民區"], max_price=1150, max_pages=1
    )
    options = crawler._launch_options()
    assert options["headless"] is False
    assert "--window-position=-32000,-32000" in options["args"]


def test_show_browser_mode_does_not_move_window_offscreen():
    crawler = BrowserRakuyaPilotCrawler(
        districts=["三民區"], max_price=1150, max_pages=1,
        background=False,
    )
    assert crawler._launch_options() == {"headless": False}


def test_select_detail_candidates_filters_numeric_requirements_and_deduplicates():
    profile = {
        "min_main_area": 15,
        "min_rooms": 2,
        "preferred_max_age": 35,
        "min_floor_ratio": 2 / 3,
    }
    base = {
        "source": "樂屋網", "title": "候選", "city": "高雄市",
        "district": "三民區", "total_price_wan": 1000,
        "property_type": "電梯大樓", "main_area_ping": 16,
        "rooms": 2, "age_years": 20, "current_floor": 10,
        "total_floors": 12, "community": "同社區",
    }
    first = HomeListing(external_id="1", url="https://example.com/1", **base)
    duplicate_ad = HomeListing(external_id="2", url="https://example.com/2", **base)
    too_low = HomeListing(
        external_id="3", url="https://example.com/3",
        **{**base, "community": "另一社區", "current_floor": 2},
    )
    selected = select_detail_candidates([first, duplicate_ad, too_low], profile)
    assert [item.external_id for item in selected] == ["1"]


def test_compare_with_current_uses_conservative_physical_key():
    base = {
        "city": "高雄市", "district": "三民區", "property_type": "電梯大樓",
        "total_area_ping": 45.93, "rooms": 4, "current_floor": 13,
        "community": "聖田市",
    }
    current = HomeListing(
        source="591中古屋", external_id="591-1", title="現有房源",
        url="https://example.com/591", total_price_wan=998, **base
    )
    duplicate = HomeListing(
        source="樂屋網", external_id="R-1", title="樂屋同屋",
        url="https://example.com/rakuya/1", total_price_wan=1000, **base
    )
    duplicate_second_ad = HomeListing(
        source="樂屋網", external_id="R-1B", title="另一房仲刊登同屋",
        url="https://example.com/rakuya/1b", total_price_wan=998, **base
    )
    potential_new = HomeListing(
        source="樂屋網", external_id="R-2", title="樂屋另一間",
        url="https://example.com/rakuya/2", city="高雄市", district="三民區",
        total_price_wan=900, property_type="公寓", total_area_ping=30,
        rooms=3, current_floor=4, address="民族一路",
    )
    result = compare_with_current([duplicate, duplicate_second_ad, potential_new], [current])
    assert result["overlap_count"] == 2
    assert result["overlap_distinct_property_count"] == 1
    assert result["pilot_distinct_property_count"] == 2
    assert result["pilot_intra_source_duplicate_group_count"] == 1
    assert result["pilot_intra_source_duplicate_ad_count"] == 1
    assert result["potential_new_count"] == 1
    assert result["overlaps"][0]["matches"][0]["source"] == "591中古屋"
