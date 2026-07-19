from email.message import Message

import pytest

from home_finder.live_sources import (
    CachedHttpClient,
    Sale591PublicHtmlSource,
    parse_591_sale_html,
)


HTML = """
<html><body>
  <a href="https://sale.591.com.tw/home/house/detail/2/20132645.html">
    <span>8分鐘前更新</span><span>近一週406次曝光</span>
    <strong>設籍金華學區高樓景觀電梯3房</strong>
    <span>大安區</span><span>3房2廳2衛</span><span>29.3坪</span>
    <span>3,980 萬</span><span>153.31萬/坪</span>
  </a>
  <a href="/home/house/detail/2/20559578.html">
    18分鐘前更新 近一週39次曝光 中和街零公設一樓 北投區 3房2廳2衛 32.1坪 1,580 萬 49.22萬/坪
  </a>
</body></html>
"""


def test_parse_591_public_html() -> None:
    listings = parse_591_sale_html(HTML, "台北市")
    assert len(listings) == 2
    assert listings[0].id == "20132645"
    assert listings[0].title == "設籍金華學區高樓景觀電梯3房"
    assert listings[0].district == "大安區"
    assert listings[0].rooms == 3
    assert listings[0].area_ping == 29.3
    assert listings[0].total_price_wan == 3980
    assert listings[0].tags == ("電梯",)
    assert listings[1].url.startswith("https://sale.591.com.tw/")


class FakeResponse:
    def __init__(self, body: str) -> None:
        self.body = body.encode("utf-8")
        self.headers = Message()
        self.headers["Content-Type"] = "text/html; charset=utf-8"

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self) -> bytes:
        return self.body


def test_http_cache_avoids_second_request(tmp_path) -> None:
    calls = []

    def opener(request, timeout):
        calls.append((request.full_url, timeout))
        return FakeResponse(HTML)

    client = CachedHttpClient(cache_dir=tmp_path, opener=opener)
    first, first_cached = client.get_text("https://example.com/search?a=1")
    second, second_cached = client.get_text("https://example.com/search?a=1")
    assert first == second == HTML
    assert first_cached is False
    assert second_cached is True
    assert len(calls) == 1


def test_591_source_deduplicates_pages() -> None:
    class FakeClient:
        def get_text(self, url):
            return HTML, True

    source = Sale591PublicHtmlSource(
        city="台北市", region_id=1, pages=2, client=FakeClient(), sleep=lambda _: None
    )
    assert len(source.fetch()) == 2


def test_591_source_enforces_request_delay() -> None:
    with pytest.raises(ValueError, match="不可小於 2"):
        Sale591PublicHtmlSource(city="台北市", region_id=1, delay_seconds=0)
