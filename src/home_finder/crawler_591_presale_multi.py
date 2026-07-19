from __future__ import annotations

from contextlib import ExitStack
from dataclasses import replace

from playwright.sync_api import sync_playwright

from .crawler_591_presale import SECTION_IDS, parse_presale_detail
from .crawler_591_presale_v2 import Browser591PresaleCrawler, parse_presale_card
from .user_models import HomeListing


class MultiDistrict591PresaleCrawler(Browser591PresaleCrawler):
    """591 預售屋沒有有效 page=2；逐區讀取完整首批列表。"""

    def fetch(self) -> list[HomeListing]:
        candidates: list[HomeListing] = []
        seen: set[str] = set()
        cache = self._load_cache()
        with sync_playwright() as playwright, ExitStack() as cleanup:
            browser = self._launch(playwright)
            cleanup.callback(lambda: browser.is_connected() and browser.close())
            context = browser.new_context(locale="zh-TW")
            list_page = context.new_page()
            for index, district in enumerate(self.districts):
                if index:
                    self.sleep(self.delay_seconds)
                url = (
                    "https://newhouse.591.com.tw/list?type=1&regionid=17&sectionid="
                    f"{SECTION_IDS[district]}"
                )
                list_page.goto(url, wait_until="domcontentloaded", timeout=30000)
                list_page.wait_for_timeout(2500)
                for payload in self._card_payloads(list_page):
                    if "預售屋" not in (payload.get("text") or ""):
                        continue
                    try:
                        listing = parse_presale_card(payload)
                    except ValueError:
                        continue
                    listing = replace(listing, search_profile="預售屋")
                    if listing.external_id not in seen and (listing.rooms or 0) >= 2:
                        seen.add(listing.external_id)
                        candidates.append(listing)

            detailed: list[HomeListing] = []
            detail_page = context.new_page()
            uncached_requests = 0
            for listing in candidates[: self.max_details]:
                cached_data = cache.get(listing.external_id)
                if cached_data:
                    cached = HomeListing.from_dict(cached_data)
                    detailed.append(
                        replace(
                            cached,
                            title=listing.title,
                            url=listing.url,
                            district=listing.district,
                            total_price_wan=listing.total_price_wan,
                            rooms=listing.rooms,
                            total_area_ping=listing.total_area_ping,
                            search_profile="預售屋",
                        )
                    )
                    continue
                if uncached_requests:
                    self.sleep(self.delay_seconds)
                uncached_requests += 1
                detail_page.goto(listing.url, wait_until="domcontentloaded", timeout=30000)
                detail_page.locator("body").wait_for(timeout=15000)
                detail_page.wait_for_timeout(1200)
                item = parse_presale_detail(listing, detail_page.locator("body").inner_text())
                detailed.append(item)
                cache[item.external_id] = item.to_dict()
                self._save_cache(cache)
            browser.close()
        return detailed
