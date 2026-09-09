from home_finder.crawler_leju_presale import BrowserLejuPresaleCrawler, parse_leju_card


def test_parse_leju_project_keeps_unknown_total_price_for_map_discovery():
    listing = parse_leju_card(
        {
            "href": "/community/L2a01144327d055?mode=buy",
            "title": "築蜻蜓 ",
            "address": "清平街78巷16號",
            "text": (
                "築蜻蜓 開價 待定 清平街78巷16號 屋齡 1 年 "
                "公設比 25% 總戶數 40戶 開放式 -- 1房 -- "
                "2房 25~26 坪 3房 29~35 坪 4房+ --"
            ),
        },
        "楠梓區",
    )
    assert listing.source == "樂居新建案"
    assert listing.external_id == "L2a01144327d055"
    assert listing.title == "築蜻蜓"
    assert listing.total_price_wan == 0
    assert listing.total_area_ping == 25
    assert listing.main_area_ping is None
    assert listing.rooms == 2
    assert listing.address == "清平街78巷16號"
    assert any("總價" in warning for warning in listing.data_warnings)


def test_parse_leju_unit_price_is_not_misread_as_total_price():
    listing = parse_leju_card(
        {
            "href": "/community/L93813139345d9c?mode=buy",
            "title": "鑫時代",
            "address": "楠陽路",
            "text": "開價 34~41萬 /坪 預計 2026年06月完工 公設比 35% 總戶數 528戶 2房 24~26 坪",
        },
        "楠梓區",
    )
    assert listing.total_price_wan == 0
    assert any("34～41 萬／坪" in warning for warning in listing.data_warnings)


def test_leju_browser_runs_offscreen_by_default():
    crawler = BrowserLejuPresaleCrawler(["楠梓區"])
    assert crawler.headless is False
    assert crawler.background is True
