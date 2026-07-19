from __future__ import annotations

import json
import re
import time
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Protocol
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .models import Listing


class ListingSource(Protocol):
    def fetch(self) -> list[Listing]: ...


class JsonFileSource:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def fetch(self) -> list[Listing]:
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise ValueError("房源 JSON 最外層必須是陣列")
        return [Listing.from_dict(item) for item in raw]


class _ListingAnchorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._href: str | None = None
        self._text: list[str] = []
        self.anchors: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a" and self._href is None:
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None and data.strip():
            self._text.append(data.strip())

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href is not None:
            self.anchors.append((self._href, " ".join(self._text)))
            self._href = None
            self._text = []


_DETAIL_ID = re.compile(r"/home/house/detail/\d+/(?P<id>\d+)\.html")
_LISTING_SUMMARY = re.compile(
    r"(?P<district>[\u4e00-\u9fff]{1,8}區)\s+"
    r"(?:(?P<rooms>\d+(?:\.\d+)?)房(?:\d+廳)?(?:\d+衛)?\s+)?"
    r"(?P<area>\d+(?:\.\d+)?)坪\s+"
    r"(?P<price>[\d,]+(?:\.\d+)?)\s*萬(?:\s+[\d,.]+萬/坪)?\s*$"
)


def parse_591_sale_html(html: str, city: str) -> list[Listing]:
    """解析 591 公開搜尋頁伺服器 HTML 中已出現的房源連結。"""

    parser = _ListingAnchorParser()
    parser.feed(html)
    results: list[Listing] = []
    seen: set[str] = set()

    for href, text in parser.anchors:
        id_match = _DETAIL_ID.search(href)
        summary_match = _LISTING_SUMMARY.search(text)
        if not id_match or not summary_match:
            continue
        listing_id = id_match.group("id")
        if listing_id in seen:
            continue
        seen.add(listing_id)

        title = text[: summary_match.start()].strip()
        title = re.sub(r"^.*?近一週[\d,]+次曝光\s*", "", title).strip()
        title = re.sub(r"^.*?更新\s*", "", title).strip()
        if not title:
            title = f"591 房源 {listing_id}"

        url = href if href.startswith("https://") else f"https://sale.591.com.tw{href}"
        tags = tuple(
            word
            for word in ("近捷運", "車位", "電梯", "陽台", "屋主", "降價", "急售")
            if word in title
        )
        results.append(
            Listing(
                id=listing_id,
                title=title,
                url=url,
                city=city,
                district=summary_match.group("district"),
                total_price_wan=float(summary_match.group("price").replace(",", "")),
                area_ping=float(summary_match.group("area")),
                rooms=float(summary_match.group("rooms") or 0),
                tags=tags,
                source="591-sale-public-html",
            )
        )
    return results


class CachedHttpClient:
    def __init__(
        self,
        cache_dir: str | Path = "data/cache",
        cache_ttl_seconds: int = 3600,
        timeout_seconds: int = 20,
        opener: Callable[..., Any] = urlopen,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_ttl_seconds = max(0, cache_ttl_seconds)
        self.timeout_seconds = timeout_seconds
        self.opener = opener

    def get_text(self, url: str) -> tuple[str, bool]:
        cache_key = sha256(url.encode("utf-8")).hexdigest()[:20]
        cache_path = self.cache_dir / f"{cache_key}.html"
        if cache_path.exists():
            age = time.time() - cache_path.stat().st_mtime
            if age <= self.cache_ttl_seconds:
                return cache_path.read_text(encoding="utf-8"), True

        request = Request(
            url,
            headers={
                "User-Agent": "home-finder/0.1 (personal-use; low-frequency)",
                "Accept-Language": "zh-TW,zh;q=0.9",
            },
        )
        with self.opener(request, timeout=self.timeout_seconds) as response:
            content_type = response.headers.get_content_type()
            if content_type != "text/html":
                raise RuntimeError(f"預期 HTML，實際收到 {content_type}")
            html = response.read().decode("utf-8", errors="replace")

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(html, encoding="utf-8")
        return html, False


class Sale591PublicHtmlSource:
    BASE_URL = "https://sale.591.com.tw/"

    def __init__(
        self,
        city: str,
        region_id: int,
        pages: int = 1,
        delay_seconds: float = 3.0,
        client: CachedHttpClient | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not city.strip():
            raise ValueError("591 資料源需要 city")
        if region_id <= 0:
            raise ValueError("591 資料源需要正整數 region_id")
        if not 1 <= pages <= 5:
            raise ValueError("pages 必須介於 1 到 5")
        if delay_seconds < 2:
            raise ValueError("為降低網站負擔，delay_seconds 不可小於 2")
        self.city = city
        self.region_id = region_id
        self.pages = pages
        self.delay_seconds = delay_seconds
        self.client = client or CachedHttpClient()
        self.sleep = sleep

    def fetch(self) -> list[Listing]:
        listings: list[Listing] = []
        seen: set[str] = set()
        previous_request_used_network = False

        for page in range(self.pages):
            if page and previous_request_used_network:
                self.sleep(self.delay_seconds)
            query = urlencode(
                {"regionid": self.region_id, "shType": "list", "firstRow": page * 30}
            )
            html, from_cache = self.client.get_text(f"{self.BASE_URL}?{query}")
            previous_request_used_network = not from_cache
            for listing in parse_591_sale_html(html, self.city):
                if listing.id not in seen:
                    seen.add(listing.id)
                    listings.append(listing)

        if not listings:
            raise RuntimeError(
                "591 公開 HTML 沒有可解析的房源；網站版型可能已改變，或此頁只提供前端動態內容"
            )
        return listings
