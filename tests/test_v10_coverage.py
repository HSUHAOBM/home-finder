from __future__ import annotations

import copy

import pytest

from home_finder import web_app_v7, web_app_v10
from home_finder.crawler_591_browser import DETAIL_PRICE
from home_finder.crawler_591_multi import PROFILE_SHAPES as PROFILE_SHAPES_591
from home_finder.crawler_yungching import PROFILE_TYPES as PROFILE_TYPES_YUNGCHING
from home_finder.user_models import HomeListing
from home_finder.user_ranking_v6 import evaluate_all


def listing(**changes) -> HomeListing:
    values = dict(
        source="591中古屋",
        external_id="A",
        title="測試房源",
        url="https://sale.591.com.tw/home/house/detail/2/1.html",
        city="高雄市",
        district="楠梓區",
        total_price_wan=1188,
        property_type="電梯大樓",
        main_area_ping=18,
        rooms=3,
        baths=2,
        age_years=5,
        current_floor=10,
        total_floors=15,
        parking_type="平面式",
        has_parking=True,
        search_profile="大樓公寓華廈",
    )
    values.update(changes)
    return HomeListing(**values)


def test_condo_sources_do_not_collect_apartments():
    assert PROFILE_SHAPES_591["大樓公寓華廈"] == ("電梯大樓", "華廈")
    assert "公寓" not in PROFILE_TYPES_YUNGCHING["大樓公寓華廈"]


def test_existing_apartments_are_removed_during_evaluation():
    settings = copy.deepcopy(web_app_v7.load_settings())

    results = evaluate_all(
        [listing(property_type="公寓"), listing(external_id="B")], settings
    )

    assert {result.listing.external_id for result in results} == {"B"}


def test_full_scan_has_no_publish_day_limit_and_collects_to_1300(monkeypatch):
    captured = {}

    class FakeCrawler:
        cache_expired = False
        stats = {}

        def __init__(self, **kwargs):
            captured.update(kwargs)

        def fetch(self):
            return []

    monkeypatch.setattr(web_app_v7, "TimedResaleCrawler", FakeCrawler)
    settings = copy.deepcopy(web_app_v7.load_settings())

    _, diagnostics = web_app_v7._crawl_for_mode(
        "大樓公寓華廈",
        settings,
        {"collection_max_price": 1300},
        "full",
    )

    assert captured["max_pages"] == 10
    assert captured["publish_days"] == 0
    assert captured["collection_max_price"] == 1300
    assert diagnostics["publish_days"] == 0


def test_manual_url_import_merges_into_existing_results(monkeypatch, tmp_path):
    captured = {}
    timestamps = iter([100.0, 225.4])
    current_settings = copy.deepcopy(web_app_v7.load_settings())

    class FakeCrawler:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def fetch_url(self, url):
            captured["url"] = url
            return listing(external_id="20564796")

    monkeypatch.setattr(web_app_v10.crawl_app, "TimedResaleCrawler", FakeCrawler)
    monkeypatch.setattr(web_app_v10, "_monotonic", lambda: next(timestamps))
    monkeypatch.setattr(
        web_app_v10.crawl_app, "load_settings",
        lambda: copy.deepcopy(current_settings),
    )
    monkeypatch.setattr(
        web_app_v10.listing_app, "_load_existing_listings", lambda: []
    )
    monkeypatch.setattr(
        web_app_v10, "annotate_history", lambda items, path: items
    )
    monkeypatch.setattr(
        web_app_v10.result_app, "_write_results",
        lambda records: captured.update(records=records),
    )
    monkeypatch.setattr(
        web_app_v10.previous.previous, "load_dashboard_payload",
        lambda: {"groups": {}},
    )
    config_path = tmp_path / "config.user.json"
    config_path.write_text('{"source":{"collection_max_price":1300}}', encoding="utf-8")
    monkeypatch.setattr(web_app_v10.base, "CONFIG_PATH", config_path)

    with web_app_v10.base._state_lock:
        web_app_v10.base._state["running"] = False

    response = web_app_v10.app.test_client().post(
        "/api/listings/import",
        json={
            "profile": "大樓公寓華廈",
            "url": "https://sale.591.com.tw/home/house/detail/2/20564796.html",
        },
    )

    assert response.status_code == 200
    assert response.get_json()["listing_id"] == "20564796"
    assert captured["collection_max_price"] == 1300
    assert captured["records"]
    assert web_app_v10.base._state_snapshot()["duration_seconds"] == 125.4

def test_direct_591_url_parses_and_keeps_1290_listing(monkeypatch):
    from home_finder import crawler_591_multi

    body = """高雄市 楠梓區
1,290 萬元
3房2廳2衛
12F/15F
權狀坪數 41.99坪
屋齡 11年
房屋資料
現況：住宅
型態：電梯大樓 裝潢程度：簡易裝潢
車位：5.411坪，平面式，已含售金內 坪數說明
主建物：21.35坪
"""

    class FakeLocator:
        def __init__(self, text):
            self.text = text

        @property
        def first(self):
            return self

        def wait_for(self, **_kwargs):
            return None

        def inner_text(self):
            return self.text

    class FakePage:
        def goto(self, url, **_kwargs):
            self.url = url

        def wait_for_timeout(self, _milliseconds):
            return None

        def locator(self, selector):
            return FakeLocator("三發景榮高樓三房" if selector == "h1" else body)

    class FakeBrowser:
        def __init__(self):
            self.page = FakePage()

        def new_page(self, **_kwargs):
            return self.page

        def is_connected(self):
            return True

        def close(self):
            return None

    class FakePlaywrightContext:
        def __enter__(self):
            return object()

        def __exit__(self, *_args):
            return None

    subject = crawler_591_multi.MultiPage591ResaleCrawler(
        profile="大樓公寓華廈",
        districts=["楠梓區"],
        max_pages=3,
        publish_days=5,
        max_details=1,
        collection_max_price=1300,
        sleep=lambda _seconds: None,
    )
    monkeypatch.setattr(crawler_591_multi, "sync_playwright", FakePlaywrightContext)
    monkeypatch.setattr(subject, "_launch", lambda _playwright: FakeBrowser())

    result = subject.fetch_url(
        "https://sale.591.com.tw/home/house/detail/2/20579287.html"
    )

    assert result.external_id == "20579287"
    assert result.total_price_wan == 1290
    assert result.property_type == "電梯大樓"
    assert result.main_area_ping == 21.35
    assert result.parking_type == "5.411坪，平面式，已含售金內"
    assert result.current_floor == 12
    assert result.total_floors == 15


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("638 萬元 有議價空間嗎？", "638"),
        ("650 萬元 有議價空間嗎？", "650"),
        ("698 萬元 有議價空間嗎？", "698"),
        ("1,188 萬元 有議價空間嗎？", "1,188"),
        ("1,290 萬元 有議價空間嗎？", "1,290"),
        ("1,290\n萬", "1,290"),
    ],
)
def test_price_parser_accepts_current_and_legacy_591_formats(text, expected):
    match = DETAIL_PRICE.search(text)

    assert match is not None
    assert match.group("price") == expected
