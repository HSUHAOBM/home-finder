from __future__ import annotations

import re
from contextlib import ExitStack
from dataclasses import replace
from pathlib import Path
from urllib.parse import urlencode, urljoin

from playwright.sync_api import (
    BrowserContext,
    Page,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)

from .crawler_591_browser import parse_detail_text, parse_list_card
from .crawler_591_browser_v3 import Browser591Crawler
from .user_models import HomeListing


PROFILE_SHAPES = {
    "大樓公寓華廈": ("電梯大樓", "華廈", "公寓"),
    "透天別墅": ("透天厝", "別墅"),
}
PROFILE_TYPES = {
    "大樓公寓華廈": {"電梯大樓", "華廈", "公寓"},
    "透天別墅": {"透天厝", "別墅"},
}
UPDATE_TEXT = re.compile(r"(?:剛剛|\d+\s*(?:分鐘|小時|天)前|今天|昨日|昨天)\s*更新")
MAX_DISTRICTS_PER_SEARCH = 5


class MultiPage591ResaleCrawler(Browser591Crawler):
    def __init__(
        self,
        profile: str,
        districts: list[str],
        max_pages: int = 3,
        publish_days: int = 3,
        max_details: int = 50,
        **kwargs,
    ) -> None:
        super().__init__(districts=districts, max_details=max_details, **kwargs)
        if profile not in PROFILE_SHAPES:
            raise ValueError(f"不支援的中古屋目標：{profile}")
        if not 3 <= max_pages <= 10:
            raise ValueError("max_pages 必須介於 3 到 10")
        if publish_days not in {0, 1, 3, 5, 7, 15, 30}:
            raise ValueError("publish_days 不支援")
        self.profile = profile
        self.max_pages = max_pages
        self.publish_days = publish_days

    def _select_shapes(self, page: Page) -> None:
        for shape in PROFILE_SHAPES[self.profile]:
            label = page.locator("label").filter(has_text=re.compile(rf"^\s*{re.escape(shape)}\s*$"))
            if label.count():
                label.first.click()
                page.wait_for_timeout(700)
        page.wait_for_timeout(2500)

    def _read_profile_cards(self, page: Page) -> list[HomeListing]:
        try:
            page.locator(".ware-item").first.wait_for(timeout=8000)
        except PlaywrightTimeoutError:
            return []
        payloads = page.locator(".ware-item").evaluate_all(
            """cards => cards.map(card => {
                const header = card.querySelector('.ware-item__header a');
                const district = card.querySelector('.ware-item__section');
                const community = card.querySelector('.ware-item__community-link');
                const address = card.querySelector('.ware-item__address');
                return {
                    text: card.innerText || '', href: header ? header.href : '',
                    title: header ? (header.getAttribute('title') || header.innerText) : '',
                    district: district ? district.innerText : '',
                    community: community ? community.innerText : null,
                    address: address ? address.innerText : null
                };
            })"""
        )
        listings: list[HomeListing] = []
        for payload in payloads:
            payload["href"] = urljoin("https://sale.591.com.tw", payload.get("href") or "")
            try:
                listing = parse_list_card(payload, "高雄市")
            except ValueError:
                continue
            updated = UPDATE_TEXT.search(payload.get("text") or "")
            listing = replace(
                listing,
                search_profile=self.profile,
                listing_updated_text=updated.group(0) if updated else None,
            )
            if (
                listing.district in self.districts
                and listing.total_price_wan <= 1200
                and listing.property_type in PROFILE_TYPES[self.profile]
            ):
                listings.append(listing)
        return listings

    @staticmethod
    def _merge_cached(current: HomeListing, cached: HomeListing) -> HomeListing:
        return replace(
            cached,
            title=current.title,
            url=current.url,
            district=current.district,
            total_price_wan=current.total_price_wan,
            total_area_ping=current.total_area_ping,
            rooms=current.rooms,
            living_rooms=current.living_rooms,
            baths=current.baths,
            age_years=current.age_years,
            current_floor=current.current_floor,
            total_floors=current.total_floors,
            community=current.community,
            address=current.address,
            tags=current.tags,
            search_profile=current.search_profile,
            listing_updated_text=current.listing_updated_text,
        )

    def _district_batches(self) -> list[list[str]]:
        batch_count = max(
            1,
            (len(self.districts) + MAX_DISTRICTS_PER_SEARCH - 1)
            // MAX_DISTRICTS_PER_SEARCH,
        )
        batch_size, larger_batches = divmod(len(self.districts), batch_count)
        batches: list[list[str]] = []
        offset = 0
        for index in range(batch_count):
            size = batch_size + (1 if index < larger_batches else 0)
            batches.append(self.districts[offset : offset + size])
            offset += size
        return batches

    def _fetch_batch_candidates(
        self, context: BrowserContext, districts: list[str]
    ) -> list[HomeListing]:
        original_districts = self.districts
        self.districts = districts
        list_page = context.new_page()
        try:
            query = {"regionid": 17, "firstRow": 0, "shType": "list"}
            if self.publish_days:
                query["publish_day"] = self.publish_days
            list_page.goto(
                "https://sale.591.com.tw/?" + urlencode(query),
                wait_until="domcontentloaded",
                timeout=30000,
            )
            self._select_districts(list_page)
            self._select_shapes(list_page)

            candidates: list[HomeListing] = []
            seen: set[str] = set()
            for page_number in range(1, self.max_pages + 1):
                if page_number > 1:
                    next_link = list_page.get_by_role("link", name="下一頁", exact=True)
                    if not next_link.count():
                        break
                    next_url = urljoin(
                        "https://sale.591.com.tw",
                        next_link.first.get_attribute("href") or "",
                    )
                    if not next_url:
                        break
                    self.sleep(self.delay_seconds)
                    list_page.goto(
                        next_url, wait_until="domcontentloaded", timeout=30000
                    )
                    list_page.wait_for_timeout(1800)
                page_listings = self._read_profile_cards(list_page)
                if not page_listings:
                    break
                for listing in page_listings:
                    if listing.external_id not in seen:
                        seen.add(listing.external_id)
                        candidates.append(listing)
            return candidates
        finally:
            self.districts = original_districts
            list_page.close()

    def _collect_candidates(self, context: BrowserContext) -> list[HomeListing]:
        batch_candidates = [
            self._fetch_batch_candidates(context, districts)
            for districts in self._district_batches()
        ]
        candidates: list[HomeListing] = []
        seen: set[str] = set()
        max_batch_size = max((len(batch) for batch in batch_candidates), default=0)
        for item_index in range(max_batch_size):
            for batch in batch_candidates:
                if item_index >= len(batch):
                    continue
                listing = batch[item_index]
                if listing.external_id not in seen:
                    seen.add(listing.external_id)
                    candidates.append(listing)
        return candidates

    def fetch(self) -> list[HomeListing]:
        cache = self._load_cache()
        with sync_playwright() as playwright, ExitStack() as cleanup:
            browser = self._launch(playwright)
            cleanup.callback(lambda: browser.is_connected() and browser.close())
            context = browser.new_context(locale="zh-TW")
            candidates = self._collect_candidates(context)

            detailed: list[HomeListing] = []
            detail_page = context.new_page()
            uncached_requests = 0
            for listing in candidates[: self.max_details]:
                cached_data = cache.get(listing.external_id)
                if cached_data:
                    detailed.append(self._merge_cached(listing, HomeListing.from_dict(cached_data)))
                    continue
                if uncached_requests:
                    self.sleep(self.delay_seconds)
                uncached_requests += 1
                try:
                    detail_page.goto(listing.url, wait_until="domcontentloaded", timeout=30000)
                    detail_page.locator("body").wait_for(timeout=15000)
                    detail_page.wait_for_timeout(1200)
                    item = parse_detail_text(listing, detail_page.locator("body").inner_text())
                except Exception as exc:
                    item = replace(
                        listing,
                        lifecycle_status="possibly_removed",
                        data_warnings=listing.data_warnings + [f"詳情頁讀取失敗：{type(exc).__name__}"],
                    )
                detailed.append(item)
                cache[item.external_id] = item.to_dict()
                self._save_cache(cache)
            browser.close()
        return detailed
