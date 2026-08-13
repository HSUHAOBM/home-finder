from home_finder.crawler_591_browser import parse_detail_text, parse_list_card
from home_finder.user_models import HomeListing
from home_finder.user_ranking import evaluate_listing, find_duplicate_groups


def home(**changes) -> HomeListing:
    values = {
        "source": "test",
        "external_id": "1",
        "title": "高樓兩房平車",
        "url": "https://example.com/1",
        "city": "高雄市",
        "district": "楠梓區",
        "total_price_wan": 1100,
        "property_type": "電梯大樓",
        "main_area_ping": 16,
        "rooms": 2,
        "baths": 2,
        "age_years": 10,
        "current_floor": 9,
        "total_floors": 10,
        "parking_type": "坡道平面",
        "has_parking": True,
    }
    values.update(changes)
    return HomeListing(**values)


def test_condo_flat_parking_is_hard_requirement() -> None:
    result = evaluate_listing(home(parking_type="機械", has_parking=True), "大樓公寓華廈")
    assert result.status == "rejected"
    assert result.hard_failures == ["不是平面車位：機械"]


def test_unknown_parking_does_not_pass() -> None:
    result = evaluate_listing(home(parking_type=None, has_parking=None), "大樓公寓華廈")
    assert result.status == "needs_verification"
    assert "汽車位資料不明" in result.missing_required


def test_title_cannot_turn_condo_into_villa() -> None:
    result = evaluate_listing(home(title="稀有車墅", property_type="電梯大樓"), "透天別墅")
    assert result.status == "rejected"
    assert "排除疑似混入的車墅廣告" in result.hard_failures[0]


def test_detail_structured_parking_overrides_title() -> None:
    listing = home(title="三房平車", parking_type=None, has_parking=None)
    body = "房屋資料 型態 ： 電梯大樓 裝潢程度 ： 簡易裝潢 車位 ： 無 坪數說明 主建物 ： 19.938坪"
    enriched = parse_detail_text(listing, body)
    assert enriched.has_parking is False
    assert enriched.parking_type == "無"
    assert "標題宣稱平車" in enriched.data_warnings[0]


def test_detail_text_uses_complete_kaohsiung_address_when_present() -> None:
    listing = home(
        external_id="20575470", title="小康成家", address="高楠公路",
        community="小康成家",
    )
    enriched = parse_detail_text(
        listing,
        "房屋資料 地址：高雄市楠梓區高楠公路1749號 型態：電梯大樓 裝潢程度：精緻裝潢",
    )
    assert enriched.address == "高雄市楠梓區高楠公路1749號"


def test_duplicate_group_ignores_different_asking_prices() -> None:
    first = home(external_id="a", community="希望社區", total_area_ping=31.2)
    second = home(external_id="b", community="希望社區", total_area_ping=31.2, total_price_wan=1150)
    assert find_duplicate_groups([first, second]) == {
        "test:a": ["test:b"],
        "test:b": ["test:a"],
    }


def test_parse_realistic_list_card() -> None:
    card = {
        "text": "標題\n電梯大樓\n3房2廳2衛\n權狀40.74坪\n主建19.94坪\n13年\n10F/12F\n含車位\n1,058\n萬\n25.97萬/坪",
        "href": "https://sale.591.com.tw/home/house/detail/2/20514872.html",
        "title": "高樓三房平車",
        "district": "三民區-",
        "community": "測試社區",
        "address": "建工路",
    }
    listing = parse_list_card(card, "高雄市")
    assert listing.external_id == "20514872"
    assert listing.total_price_wan == 1058
    assert listing.main_area_ping == 19.94
    assert listing.current_floor == 10
    assert listing.total_floors == 12


def test_list_card_ignores_discount_amount_before_total_price() -> None:
    card = {
        "text": (
            "降價\n70\n萬\n電梯大樓\n3房2廳2衛\n"
            "權狀57.74坪\n9F/15F\n1,188\n萬\n"
        ),
        "href": "https://sale.591.com.tw/home/house/detail/2/20670982.html",
        "title": "降價三房雙平車",
        "district": "仁武區-",
        "community": "測試社區",
        "address": "測試路",
    }

    listing = parse_list_card(card, "高雄市")

    assert listing.total_price_wan == 1188
