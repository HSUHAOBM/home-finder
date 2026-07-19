from home_finder.crawler_591_presale import parse_presale_card, parse_presale_detail
from home_finder.user_ranking_v2 import evaluate_listing


def test_presale_unknown_price_and_main_area_need_verification() -> None:
    payload = {
        "text": "白隅 高雄市楠梓區 預售屋 住宅大樓 價格待定",
        "href": "https://newhouse.591.com.tw/137589?v=720&from=list",
        "title": "白隅",
        "address": "高雄市楠梓區後勁東路",
        "room": "24~42坪 二房(24坪),三房(31~42坪)",
        "price": "價格待定",
    }
    listing = parse_presale_card(payload)
    detail = (
        "2房2廳2衛 在售 24.83坪 社區規劃 公設比 36.8% "
        "車位規劃 平面式157個 樓層規劃 地上26層"
    )
    listing = parse_presale_detail(listing, detail)
    result = evaluate_listing(listing, "預售屋")
    assert result.status == "needs_verification"
    assert "主建物坪數資料不明" in result.missing_required
    assert "汽車位資料不明" in result.missing_required
    assert "總價資料不明" in result.missing_required
    assert listing.baths == 2
    assert any("粗估室內約 15.2 坪" in warning for warning in listing.data_warnings)


def test_presale_mechanical_parking_is_rejected() -> None:
    payload = {
        "text": "測試案 高雄市橋頭區 預售屋 住宅大樓",
        "href": "https://newhouse.591.com.tw/123456",
        "title": "測試案",
        "address": "高雄市橋頭區經武路",
        "room": "二房(25坪)",
        "price": "1,100萬/戶",
    }
    listing = parse_presale_detail(
        parse_presale_card(payload),
        "2房2廳2衛 公設比 35% 車位規劃 機械式80個 樓層規劃 地上15層",
    )
    result = evaluate_listing(listing, "預售屋")
    assert result.status == "rejected"
    assert "不是平面車位" in result.hard_failures[0]
