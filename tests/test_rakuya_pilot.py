from __future__ import annotations

from home_finder.crawler_rakuya import BrowserRakuyaPilotCrawler, parse_rakuya_list_card
from home_finder.rakuya_pilot import compare_with_current
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
    potential_new = HomeListing(
        source="樂屋網", external_id="R-2", title="樂屋另一間",
        url="https://example.com/rakuya/2", city="高雄市", district="三民區",
        total_price_wan=900, property_type="公寓", total_area_ping=30,
        rooms=3, current_floor=4, address="民族一路",
    )
    result = compare_with_current([duplicate, potential_new], [current])
    assert result["overlap_count"] == 1
    assert result["potential_new_count"] == 1
    assert result["overlaps"][0]["matches"][0]["source"] == "591中古屋"
