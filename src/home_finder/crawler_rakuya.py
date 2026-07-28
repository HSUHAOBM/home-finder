from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlencode, urlparse

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from .user_models import HomeListing

SOURCE_NAME = "樂屋網"
BASE_URL = "https://www.rakuya.com.tw/sell/result"
DISTRICT_ZIPCODES = {
    "三民區": "807", "左營區": "813", "楠梓區": "811",
    "橋頭區": "825", "仁武區": "814", "大社區": "815",
}
PROPERTY_TYPE_MAP = {
    "電梯大廈": "電梯大樓", "電梯大樓": "電梯大樓",
    "大樓/華廈": "華廈", "華廈": "華廈", "公寓": "公寓",
}
PROPERTY_TYPES = tuple(PROPERTY_TYPE_MAP)


def _float(text: str) -> float:
    return float(text.replace(",", ""))


def _external_id(href: str) -> str | None:
    values = parse_qs(urlparse(href).query).get("ehid")
    return values[0] if values else None


def _property_type(text: str) -> str | None:
    raw = next((value for value in PROPERTY_TYPES if value in text), None)
    return PROPERTY_TYPE_MAP.get(raw) if raw else None


def _location_after_district(text: str, district: str) -> tuple[str | None, str | None]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    try:
        index = lines.index(district)
    except ValueError:
        return None, None
    if index + 1 >= len(lines):
        return None, None
    location = lines[index + 1]
    if _property_type(location) or re.fullmatch(r"\d+(?:\.\d+)?房.*", location):
        return None, None
    if re.search(r"[路街巷弄號]$", location):
        return None, location
    return location.removesuffix("待售房屋"), None


def parse_rakuya_list_card(payload: dict[str, Any]) -> HomeListing:
    href = str(payload.get("href") or "")
    listing_id = _external_id(href)
    text = str(payload.get("text") or "")
    title = str(payload.get("title") or "").strip()
    district_match = re.search(
        r"(?:待售房屋\s+)?(?P<district>三民區|左營區|楠梓區|橋頭區|仁武區|大社區)", text
    )
    prices = re.findall(r"([\d,]+(?:\.\d+)?)\s*萬(?!\s*/\s*坪)", text)
    property_type = _property_type(text)
    if not listing_id or not title or not district_match or not prices or not property_type:
        raise ValueError("樂屋房源卡缺少 ID、標題、行政區、價格或型態")

    district = district_match.group("district")
    community, address = _location_after_district(text, district)
    layout = re.search(
        r"(?P<rooms>\d+(?:\.\d+)?)房(?P<living>\d+(?:\.\d+)?)廳(?P<baths>\d+(?:\.\d+)?)衛", text
    )
    age = re.search(r"(?<!\d)([\d.]+)\s*年", text)
    floor = re.search(r"(?<![~\d])(\d+)\s*/\s*(\d+)\s*樓", text)
    total_area = re.search(r"總建\s*([\d.]+)\s*坪", text)
    main_area = re.search(r"主建\s*([\d.]+)\s*坪", text)
    warnings: list[str] = []
    parking_claim = next(
        (value for value in ("平面車位", "平車", "機械車位", "機械") if value in text), None
    )
    if parking_claim:
        warnings.append(f"樂屋列表提到「{parking_claim}」，尚未讀取詳情確認車位型式")

    return HomeListing(
        source=SOURCE_NAME, external_id=listing_id, title=title, url=href,
        city="高雄市", district=district, total_price_wan=_float(prices[-1]),
        property_type=property_type,
        total_area_ping=_float(total_area.group(1)) if total_area else None,
        main_area_ping=_float(main_area.group(1)) if main_area else None,
        rooms=_float(layout.group("rooms")) if layout else None,
        living_rooms=_float(layout.group("living")) if layout else None,
        baths=_float(layout.group("baths")) if layout else None,
        age_years=_float(age.group(1)) if age else None,
        current_floor=int(floor.group(1)) if floor else None,
        total_floors=int(floor.group(2)) if floor else None,
        community=community, address=address, parking_type=None, has_parking=None,
        data_warnings=warnings, search_profile="大樓公寓華廈",
    )


class BrowserRakuyaPilotCrawler:
    def __init__(
        self, districts: list[str], max_price: float, max_pages: int = 3,
        delay_seconds: float = 3.0, headless: bool = False,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        unsupported = [value for value in districts if value not in DISTRICT_ZIPCODES]
        if unsupported:
            raise ValueError(f"樂屋試爬尚未登錄行政區：{', '.join(unsupported)}")
        if not 1 <= max_pages <= 3:
            raise ValueError("樂屋試爬 max_pages 必須介於 1 到 3")
        if delay_seconds < 2:
            raise ValueError("為降低網站負擔，delay_seconds 不可小於 2")
        self.districts = districts
        self.max_price = float(max_price)
        self.max_pages = max_pages
        self.delay_seconds = delay_seconds
        self.headless = headless
        self.sleep = sleep
        self.stats: dict[str, Any] = {}

    def _list_url(self, page_number: int) -> str:
        query = {
            "zipcode": ",".join(DISTRICT_ZIPCODES[value] for value in self.districts),
            "agetype": "O", "price": f"0~{self.max_price:g}", "typecode": "R1,R2",
        }
        if page_number > 1:
            query["page"] = str(page_number)
        return f"{BASE_URL}?{urlencode(query)}"

    @staticmethod
    def _challenge_message(page) -> str | None:
        title = page.title()
        body = page.locator("body").inner_text(timeout=5000)
        terms = ("安全驗證", "security verification", "Cloudflare")
        if any(term.lower() in f"{title}\n{body}".lower() for term in terms):
            return "樂屋安全驗證尚未完成；請在可見 Chrome 完成驗證後再試"
        return None

    def _read_page(self, page, timeout_ms: int = 60000) -> tuple[list[HomeListing], int | None]:
        try:
            page.locator("a[href*='ehid=']").first.wait_for(timeout=timeout_ms)
        except PlaywrightTimeoutError as exc:
            message = self._challenge_message(page)
            raise RuntimeError(message or "樂屋列表逾時，沒有讀到房源卡") from exc
        total_match = re.search(
            r"共找到\s*([\d,]+)\s*筆待售房屋", page.locator("body").inner_text()
        )
        payloads = page.locator("a[href*='ehid=']").evaluate_all(
            """links => links.map(link => ({
                href: link.href || '', text: link.innerText || '',
                title: (link.querySelector('h2') || {}).innerText || ''
            }))"""
        )
        listings: list[HomeListing] = []
        seen: set[str] = set()
        for payload in payloads:
            text = str(payload.get("text") or "")
            if "總建" not in text or not str(payload.get("title") or "").strip():
                continue
            try:
                listing = parse_rakuya_list_card(payload)
            except ValueError:
                continue
            if listing.external_id in seen or listing.district not in self.districts:
                continue
            if listing.total_price_wan > self.max_price:
                continue
            seen.add(listing.external_id)
            listings.append(listing)
        if not listings:
            raise RuntimeError("樂屋頁面已開啟，但沒有可解析的主要房源卡；網站版型可能已改變")
        total = int(total_match.group(1).replace(",", "")) if total_match else None
        return listings, total

    def fetch(self) -> list[HomeListing]:
        started = time.time()
        fetched: list[HomeListing] = []
        seen: set[str] = set()
        page_counts: list[int] = []
        result_total: int | None = None
        with sync_playwright() as playwright:
            state_path = Path("data/cache/rakuya_storage_state.json").resolve()
            try:
                browser = playwright.chromium.launch(channel="chrome", headless=self.headless)
            except Exception:
                browser = playwright.chromium.launch(headless=self.headless)
            context_options: dict[str, Any] = {"locale": "zh-TW"}
            if state_path.exists():
                context_options["storage_state"] = str(state_path)
            context = browser.new_context(**context_options)
            try:
                page = context.new_page()
                for page_number in range(1, self.max_pages + 1):
                    if page_number > 1:
                        self.sleep(self.delay_seconds)
                    page.goto(self._list_url(page_number), wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_timeout(4000)
                    page_listings, current_total = self._read_page(page)
                    if result_total is None:
                        result_total = current_total
                    added = 0
                    for listing in page_listings:
                        if listing.external_id in seen:
                            continue
                        seen.add(listing.external_id)
                        fetched.append(listing)
                        added += 1
                    page_counts.append(added)
                context.storage_state(path=str(state_path))
            finally:
                context.close()
                browser.close()
        self.stats = {
            "source": SOURCE_NAME, "pages_requested": self.max_pages,
            "page_unique_counts": page_counts, "fetched": len(fetched),
            "reported_total": result_total, "headless": self.headless,
            "duration_seconds": round(time.time() - started, 1),
        }
        return fetched
