from home_finder.crawler_591_presale_v2 import parse_presale_card


def test_district_does_not_include_life_circle() -> None:
    listing = parse_presale_card(
        {
            "text": "以學MDT 高雄市楠梓區高雄大學特區 預售屋 住宅大樓",
            "href": "https://newhouse.591.com.tw/139856",
            "title": "以學MDT",
            "address": "高雄市楠梓區高雄大學特區大學西路",
            "room": "二房(26坪),三房(39坪)",
            "price": "價格待定",
        }
    )
    assert listing.district == "楠梓區"
