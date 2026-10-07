from urllib.parse import parse_qs, urlparse

from home_finder.crawler_591_multi import MultiPage591ResaleCrawler
from home_finder.web_app_v7 import _coverage_incomplete_reason, _full_scan_archive_skip_reason
from home_finder.crawler_591_browser import parse_list_card
from home_finder import web_app_v7
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError


def subject(tmp_path):
    return MultiPage591ResaleCrawler(
        profile="大樓公寓華廈", districts=["橋頭區"], max_pages=3,
        publish_days=5, audit_path=tmp_path / "trace.jsonl",
        sleep=lambda _: None,
    )


def test_query_explicitly_sets_district_and_shapes(tmp_path):
    crawler = subject(tmp_path)
    query = crawler._query_parameters(["橋頭區"])
    assert query["section"] == "263"
    assert query["shape"] == "2,5"
    assert query["publish_day"] == "5"
    assert not crawler._filters_match("https://sale.591.com.tw/?regionid=17", query)


class Link:
    @property
    def first(self):
        return self

    def count(self):
        return 1

    def get_attribute(self, name):
        # 591 gives a /list path and does not advance firstRow in href.
        return "/list?regionid=17&firstRow=0&page=2"


class Cards:
    def evaluate_all(self, script):
        return "previous-ids"


class Page:
    def __init__(self):
        self.urls = []

    def goto(self, url, **kwargs):
        self.url = url
        self.urls.append(url)

    def wait_for_timeout(self, *args):
        pass

    def wait_for_function(self, *args, **kwargs):
        pass

    def locator(self, selector):
        return Cards()

    def get_by_role(self, *args, **kwargs):
        return Link()

    def close(self):
        pass


def test_empty_accepted_page_does_not_stop_and_offsets_advance(tmp_path, monkeypatch):
    crawler = subject(tmp_path)
    page = Page()

    class Context:
        def new_page(self):
            return page

    def read(_page):
        crawler._page_read_failed = False
        return []  # Cards exist, but none meet local price/type requirements.

    monkeypatch.setattr(crawler, "_read_profile_cards", read)
    crawler._fetch_batch_candidates(Context(), ["橋頭區"], allow_split=False)
    assert len(page.urls) == 3
    for index, url in enumerate(page.urls):
        params = parse_qs(urlparse(url).query)
        assert params["firstRow"] == [str(index * 30)]
        assert params["section"] == ["263"]
        assert params["shape"] == ["2,5"]
        assert params["publish_day"] == ["5"]
        assert urlparse(url).path == "/"
    assert crawler.stats["queries"][0]["unresolved"]


def test_partial_coverage_prevents_delisting(tmp_path):
    diagnostics = {"sources": {"591": {"queries": [{
        "districts": ["橋頭區"], "unresolved": True,
        "incomplete_reason": "filters_lost", "pages_scanned": 1,
    }]}}}
    reason = _coverage_incomplete_reason(diagnostics)
    assert "橋頭區" in reason
    assert _full_scan_archive_skip_reason([], [], "大樓公寓華廈", diagnostics) == reason


def test_compact_card_uses_structured_total_price():
    card = {"href": "https://sale.591.com.tw/home/house/detail/2/25241603.html",
            "title": "橋頭測試", "district": "橋頭區-", "community": None,
            "address": None, "price_wan": "938",
            "text": "電梯大樓2房1廳1衛權狀28.93坪主建12.74坪8F/15F總價低於同社區50萬938萬32.42萬/坪"}
    listing = parse_list_card(card, "高雄市")
    assert listing.total_price_wan == 938
    assert listing.rooms == 2
    card["text"] = "電梯大樓開放式格局權狀29.89坪798萬26.7萬/坪"
    card["price_wan"] = "798"
    listing = parse_list_card(card, "高雄市")
    assert listing.rooms is None
    assert listing.data_warnings


def test_repeated_page_is_reported_as_incomplete(tmp_path, monkeypatch):
    crawler = subject(tmp_path)
    page = Page()

    class Context:
        def new_page(self):
            return page

    def read(_page):
        crawler._page_read_failed = False
        return []

    def repeated(*args, **kwargs):
        raise PlaywrightTimeoutError("same cards")

    monkeypatch.setattr(crawler, "_read_profile_cards", read)
    monkeypatch.setattr(page, "wait_for_function", repeated)
    crawler._fetch_batch_candidates(Context(), ["橋頭區"], allow_split=False)
    query = crawler.stats["queries"][0]
    assert query["unresolved"]
    assert query["incomplete_reason"] == "pagination_timeout_or_repeated_page"


def test_partial_diagnostics_do_not_become_successful_history(monkeypatch):
    monkeypatch.setattr(web_app_v7, "_load_search_history", lambda: [])
    by_profile, latest = web_app_v7._successful_crawl_summary({
        "大樓公寓華廈": {"finished_at": "2026-10-07T08:34:00+00:00",
                      "coverage_incomplete": True}
    })
    assert by_profile == {}
    assert latest is None
