from __future__ import annotations

from home_finder.crawler_yungching import (
    BrowserYungchingCrawler,
    parse_yungching_detail_text,
    parse_yungching_list_card,
)


def test_parse_yungching_discounted_list_card_uses_current_price():
    listing = parse_yungching_list_card(
        {
            "href": "https://buy.yungching.com.tw/house/7256722",
            "title": "出價就談｜悅讀時代兩房平移車位",
            "text": (
                "高雄市橋頭區新南一街 電梯大樓|0.5年|建坪28.49 "
                "2房(室)2廳2衛 5/15樓 1,098萬 40萬 1,058萬"
            ),
        }
    )
    assert listing.source == "永慶房仲網"
    assert listing.external_id == "7256722"
    assert listing.total_price_wan == 1058
    assert listing.district == "橋頭區"
    assert listing.total_area_ping == 28.49
    assert listing.current_floor == 5


def test_detail_fields_override_misleading_flat_parking_title():
    listing = parse_yungching_list_card(
        {
            "href": "/house/7256722",
            "title": "悅讀時代兩房平移車位",
            "text": "高雄市橋頭區新南一街 電梯大樓|0.5年|建坪28.49 1,058萬",
        }
    )
    body = """
悅讀時代兩房平移車位
高雄市橋頭區新南一街
1,098萬
40萬
1,058 萬
單價37.14萬/坪
電梯大樓
屋齡0.5 年
5/15樓
建物28.49坪 主+陽16.80 坪
2房(室)2廳2衛
信澤地產有限公司
基本資訊
(YC1000798)
建物坪數
28.49坪
・主建物
15.68坪
車位資訊
・車位
坡道機械固定車位
"""
    result = parse_yungching_detail_text(
        listing,
        body,
        title="悅讀時代兩房平移車位",
        headings=["高雄市橋頭區新南一街", "悅讀時代"],
        page_title="物件 | 悅讀時代 | 高雄市橋頭區住宅 | 買房 | 永慶不動產",
    )
    assert result.total_price_wan == 1058
    assert result.main_area_ping == 15.68
    assert result.rooms == 2
    assert result.baths == 2
    assert result.parking_type == "坡道機械固定車位"
    assert result.has_parking is True
    assert result.community == "悅讀時代"
    assert result.origin_source == "永慶不動產"
    assert result.origin_external_id == "YC1000798"
    assert result.broker_name == "信澤地產有限公司"
    assert "廣告標題寫平面／平移車位" in result.data_warnings[0]


def test_yungching_list_url_contains_all_districts_and_page():
    crawler = BrowserYungchingCrawler(
        profile="大樓公寓華廈",
        districts=["三民區", "橋頭區"],
        max_pages=3,
        max_details=1,
    )
    url = crawler._list_url(2)
    assert "%E4%B8%89%E6%B0%91%E5%8D%80" in url
    assert "%E6%A9%8B%E9%A0%AD%E5%8D%80" in url
    assert url.endswith("_c?pg=2")
