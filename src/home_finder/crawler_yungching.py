from __future__ import annotations

import re
import time
from contextlib import ExitStack
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote, urljoin

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from .crawler_591_browser import Browser591Crawler
from .user_models import HomeListing


SOURCE_NAME = "永慶房仲網"
BASE_URL = "https://buy.yungching.com.tw"
DETAIL_CACHE_PATH = "data/cache/yungching_details.json"
CACHE_TTL_SECONDS = 24 * 60 * 60
PROFILE_TYPES = {
    "大樓公寓華廈": {"電梯大樓", "華廈", "公寓"},
    "透天別墅": {"透天厝", "別墅"},
}
PROPERTY_TYPES = tuple(sorted(set().union(*PROFILE_TYPES.values()), key=len, reverse=True))


def _float(text: str) -> float:
    return float(text.replace(",", ""))


def _last_price(text: str) -> float | None:
    matches = re.findall(r"([\d,]+(?:\.\d+)?)\s*萬", text)
    return _float(matches[-1]) if matches else None


def _district_and_address(text: str) -> tuple[str | None, str | None]:
    match = re.search(r"高雄市(?P<district>[^\s|]{2,4}區)(?P<address>[^\s|]+)", text)
    if not match:
        return None, None
    return match.group("district"), f"高雄市{match.group('district')}{match.group('address')}"


def _property_type(text: str) -> str | None:
    return next((value for value in PROPERTY_TYPES if value in text), None)


def parse_yungching_list_card(payload: dict[str, Any]) -> HomeListing:
    href = urljoin(BASE_URL, str(payload.get("href") or ""))
    id_match = re.search(r"/house/(?P<id>\d+)", href)
    text = str(payload.get("text") or "")
    title = str(payload.get("title") or "").strip()
    if not title:
        title = next(
            (line.strip() for line in text.splitlines() if line.strip() and line.strip() != "黃金曝光"),
            "",
        )
    district, address = _district_and_address(text)
    price = _last_price(text)
    property_type = _property_type(text)
    if not id_match or not title or not district or price is None or not property_type:
        raise ValueError("永慶房源卡缺少 ID、標題、行政區、價格或型態")
    age_match = re.search(r"([\d.]+)\s*年", text)
    area_match = re.search(r"建坪\s*([\d.]+)", text)
    rooms_match = re.search(r"([\d.]+)\s*房(?:\(室\))?\s*([\d.]+)\s*廳\s*([\d.]+)\s*衛", text)
    floor_match = re.search(r"(?<![~\d])(\d+)\s*/\s*(\d+)\s*樓", text)
    return HomeListing(
        source=SOURCE_NAME,
        external_id=id_match.group("id"),
        title=title,
        url=href,
        city="高雄市",
        district=district,
        total_price_wan=price,
        property_type=property_type,
        total_area_ping=_float(area_match.group(1)) if area_match else None,
        rooms=_float(rooms_match.group(1)) if rooms_match else None,
        living_rooms=_float(rooms_match.group(2)) if rooms_match else None,
        baths=_float(rooms_match.group(3)) if rooms_match else None,
        age_years=_float(age_match.group(1)) if age_match else None,
        current_floor=int(floor_match.group(1)) if floor_match else None,
        total_floors=int(floor_match.group(2)) if floor_match else None,
        address=address,
    )


def _line_after(text: str, heading: str) -> str | None:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    try:
        index = lines.index(heading)
    except ValueError:
        return None
    for value in lines[index + 1 : index + 5]:
        cleaned = value.removeprefix("・車位").strip()
        if cleaned and cleaned not in {"・車位", "車位"}:
            return cleaned
    return None


def parse_yungching_detail_text(
    listing: HomeListing,
    body_text: str,
    *,
    title: str | None = None,
    headings: list[str] | None = None,
    page_title: str | None = None,
) -> HomeListing:
    title = (title or listing.title).strip()
    headings = [value.strip() for value in (headings or []) if value.strip()]
    price_prefix = body_text.split("單價", 1)[0]
    price = _last_price(price_prefix) or listing.total_price_wan
    district, address = _district_and_address(body_text)
    total_area = re.search(r"建物\s*([\d.]+)\s*坪", body_text)
    main_area = re.search(r"主建物\s*([\d.]+)\s*坪", body_text)
    rooms = re.search(r"([\d.]+)\s*房(?:\(室\))?\s*([\d.]+)\s*廳\s*([\d.]+)\s*衛", body_text)
    age = re.search(r"屋齡\s*([\d.]+)\s*年", body_text)
    floor = re.search(r"(?<![~\d])(\d+)\s*/\s*(\d+)\s*樓", body_text)
    origin_id_match = re.search(r"基本資訊\s*\(([A-Z0-9-]+)\)", body_text)
    origin_source_match = re.search(r"\|\s*買房\s*\|\s*([^|]+?)\s*$", page_title or "")
    broker_match = re.search(r"\n([^\n]{2,40}(?:有限公司|加盟店))\s*\n", body_text)
    parking_type = _line_after(body_text, "車位資訊")
    property_type = _property_type(body_text) or listing.property_type
    community = next((value for value in headings if value != title and not value.startswith("高雄市")), listing.community)
    warnings = list(listing.data_warnings)
    if parking_type and "機械" in parking_type and re.search(r"平面|平移", title):
        warning = f"廣告標題寫平面／平移車位，但詳情欄位為：{parking_type}"
        if warning not in warnings:
            warnings.append(warning)
    return replace(
        listing,
        title=title,
        total_price_wan=price,
        district=district or listing.district,
        address=address or listing.address,
        community=community,
        property_type=property_type,
        total_area_ping=_float(total_area.group(1)) if total_area else listing.total_area_ping,
        main_area_ping=_float(main_area.group(1)) if main_area else listing.main_area_ping,
        rooms=_float(rooms.group(1)) if rooms else listing.rooms,
        living_rooms=_float(rooms.group(2)) if rooms else listing.living_rooms,
        baths=_float(rooms.group(3)) if rooms else listing.baths,
        age_years=_float(age.group(1)) if age else listing.age_years,
        current_floor=int(floor.group(1)) if floor else listing.current_floor,
        total_floors=int(floor.group(2)) if floor else listing.total_floors,
        parking_type=parking_type or listing.parking_type,
        has_parking=True if parking_type and "無" not in parking_type else listing.has_parking,
        origin_source=origin_source_match.group(1).strip() if origin_source_match else None,
        origin_external_id=origin_id_match.group(1) if origin_id_match else None,
        broker_name=broker_match.group(1).strip() if broker_match else None,
        data_warnings=warnings,
    )


class BrowserYungchingCrawler(Browser591Crawler):
    def __init__(
        self,
        profile: str,
        districts: list[str],
        max_pages: int = 3,
        max_details: int = 20,
        max_price: float = 1200,
        delay_seconds: float = 2.0,
        headless: bool = True,
        cache_path: str | Path = DETAIL_CACHE_PATH,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        super().__init__(districts=districts, max_details=max_details, delay_seconds=delay_seconds, headless=headless, cache_path=cache_path, sleep=sleep)
        if profile not in PROFILE_TYPES:
            raise ValueError(f"永慶不支援的目標：{profile}")
        if not 1 <= max_pages <= 10:
            raise ValueError("永慶 max_pages 必須介於 1 到 10")
        self.profile = profile
        self.max_pages = max_pages
        self.max_price = float(max_price)
        self.cache_expired = False
        self.stats: dict[str, Any] = {}

    def _load_cache(self) -> dict[str, dict]:
        if self.cache_path.exists() and time.time() - self.cache_path.stat().st_mtime >= CACHE_TTL_SECONDS:
            self.cache_expired = True
            return {}
        return super()._load_cache()

    def _list_url(self, page_number: int) -> str:
        areas = ",".join(f"高雄市-{district}" for district in self.districts)
        encoded = quote(areas, safe=",-")
        suffix = f"?pg={page_number}" if page_number > 1 else ""
        return f"{BASE_URL}/list/{encoded}_c{suffix}"

    def _read_candidates(self, page) -> list[HomeListing]:
        try:
            page.locator("a[href*='house/']").first.wait_for(timeout=12000)
        except PlaywrightTimeoutError:
            return []
        payloads = page.locator("a[href*='house/']").evaluate_all("""links => links.map(link => ({href: link.href || '', text: link.innerText || '', title: (link.querySelector('img') || {}).alt || ''}))""")
        results: list[HomeListing] = []
        seen: set[str] = set()
        for payload in payloads:
            try:
                listing = parse_yungching_list_card(payload)
            except ValueError:
                continue
            if listing.external_id in seen or listing.district not in self.districts:
                continue
            if listing.property_type not in PROFILE_TYPES[self.profile] or listing.total_price_wan > self.max_price:
                continue
            seen.add(listing.external_id)
            results.append(replace(listing, search_profile=self.profile))
        return results

    @staticmethod
    def _merge_cached(current: HomeListing, cached: HomeListing) -> HomeListing:
        return replace(cached, title=current.title, url=current.url, district=current.district, property_type=current.property_type, total_area_ping=current.total_area_ping, age_years=current.age_years, address=current.address, search_profile=current.search_profile)

    def fetch(self) -> list[HomeListing]:
        cache = self._load_cache()
        candidates: list[HomeListing] = []
        seen: set[str] = set()
        detail_failures = 0
        with sync_playwright() as playwright, ExitStack() as cleanup:
            browser = self._launch(playwright)
            cleanup.callback(lambda: browser.is_connected() and browser.close())
            context = browser.new_context(locale="zh-TW")
            list_page = context.new_page()
            for page_number in range(1, self.max_pages + 1):
                if page_number > 1:
                    self.sleep(self.delay_seconds)
                list_page.goto(self._list_url(page_number), wait_until="domcontentloaded", timeout=30000)
                list_page.wait_for_timeout(3000)
                page_candidates = self._read_candidates(list_page)
                if not page_candidates:
                    break
                for listing in page_candidates:
                    if listing.external_id not in seen:
                        seen.add(listing.external_id)
                        candidates.append(listing)
            detailed: list[HomeListing] = []
            detail_page = context.new_page()
            uncached_requests = 0
            for listing in candidates[: self.max_details * 2]:
                if len(detailed) >= self.max_details:
                    break
                cached_data = cache.get(listing.external_id)
                if cached_data:
                    cached_item = self._merge_cached(listing, HomeListing.from_dict(cached_data))
                    if cached_item.total_price_wan <= self.max_price:
                        detailed.append(cached_item)
                    continue
                if uncached_requests:
                    self.sleep(self.delay_seconds)
                uncached_requests += 1
                try:
                    detail_page.goto(listing.url, wait_until="domcontentloaded", timeout=30000)
                    detail_page.locator("body").wait_for(timeout=15000)
                    detail_page.wait_for_timeout(1200)
                    item = parse_yungching_detail_text(listing, detail_page.locator("body").inner_text(), title=detail_page.locator("h1").first.inner_text(), headings=detail_page.locator("h2").all_inner_texts(), page_title=detail_page.title())
                except Exception as exc:
                    detail_failures += 1
                    item = replace(listing, lifecycle_status="possibly_removed", data_warnings=listing.data_warnings + [f"永慶詳情頁讀取失敗：{type(exc).__name__}"])
                cache[item.external_id] = item.to_dict()
                self._save_cache(cache)
                if item.total_price_wan <= self.max_price:
                    detailed.append(item)
            browser.close()
        self.stats = {"source": SOURCE_NAME, "candidate_count": len(candidates), "fetched": len(detailed), "detail_failures": detail_failures, "pages_requested": self.max_pages, "cache_expired": self.cache_expired}
        return detailed
