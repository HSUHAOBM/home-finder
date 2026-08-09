from __future__ import annotations

import re
from contextlib import ExitStack
from dataclasses import replace
from pathlib import Path
from urllib.parse import urlencode, urljoin, urlparse

from playwright.sync_api import (
    BrowserContext,
    Page,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)

from .crawler_591_browser import (
    DETAIL_ID,
    DETAIL_PRICE,
    FLOOR,
    LAYOUT,
    parse_detail_text,
    parse_list_card,
)
from .crawler_591_browser_v3 import Browser591Crawler
from .user_models import HomeListing


PROFILE_SHAPES = {
    "大樓公寓華廈": ("電梯大樓", "華廈"),
    "透天別墅": ("透天厝", "別墅"),
}
PROFILE_TYPES = {
    "大樓公寓華廈": {"電梯大樓", "華廈"},
    "透天別墅": {"透天厝", "別墅"},
}
UPDATE_TEXT = re.compile(r"(?:剛剛|\d+\s*(?:分鐘|小時|天)前|今天|昨日|昨天)\s*更新")
COLLECTION_PRICE_BANDS = ("0_500", "500_750", "750_1000", "1000_1250", "1250_1500")


class MultiPage591ResaleCrawler(Browser591Crawler):
    def __init__(
        self,
        profile: str,
        districts: list[str],
        max_pages: int = 3,
        publish_days: int = 3,
        max_details: int = 50,
        collection_max_price: float = 1300,
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
        self.collection_max_price = float(collection_max_price)
        if self.collection_max_price <= 0:
            raise ValueError("collection_max_price 必須大於 0")
        self.stats: dict[str, object] = {}

    def _select_shapes(self, page: Page, shapes: tuple[str, ...] | None = None) -> None:
        for shape in shapes or PROFILE_SHAPES[self.profile]:
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
                and listing.total_price_wan <= self.collection_max_price
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
        return [[district] for district in self.districts]

    @staticmethod
    def _interleave(groups: list[list[HomeListing]]) -> list[HomeListing]:
        results: list[HomeListing] = []
        seen: set[str] = set()
        for item_index in range(max((len(group) for group in groups), default=0)):
            for group in groups:
                if item_index >= len(group):
                    continue
                listing = group[item_index]
                if listing.external_id not in seen:
                    seen.add(listing.external_id)
                    results.append(listing)
        return results

    def _fetch_batch_candidates(
        self, context: BrowserContext, districts: list[str], *,
        price_band: str | None = None,
        shapes: tuple[str, ...] | None = None,
        allow_split: bool = True,
    ) -> list[HomeListing]:
        original_districts = self.districts
        self.districts = districts
        list_page = context.new_page()
        try:
            query = {"regionid": 17, "firstRow": 0, "shType": "list"}
            if self.publish_days:
                query["publish_day"] = self.publish_days
            if price_band:
                query["price"] = price_band
            list_page.goto(
                "https://sale.591.com.tw/?" + urlencode(query),
                wait_until="domcontentloaded",
                timeout=30000,
            )
            self._select_districts(list_page)
            self._select_shapes(list_page, shapes)

            candidates: list[HomeListing] = []
            seen: set[str] = set()
            pages_scanned = 0
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
                pages_scanned = page_number
                for listing in page_listings:
                    if listing.external_id not in seen:
                        seen.add(listing.external_id)
                        candidates.append(listing)
            next_link = list_page.get_by_role("link", name="下一頁", exact=True)
            next_href = (
                next_link.first.get_attribute("href") or ""
                if next_link.count()
                else ""
            )
            truncated = bool(next_href and pages_scanned >= self.max_pages)
            queries = self.stats.setdefault("queries", [])
            if isinstance(queries, list):
                queries.append(
                    {
                        "districts": list(districts),
                        "price_band": price_band,
                        "shapes": list(shapes or PROFILE_SHAPES[self.profile]),
                        "pages_scanned": pages_scanned,
                        "candidates": len(candidates),
                        "truncated": truncated,
                        "unresolved": bool(truncated and not allow_split),
                    }
                )
            if truncated and allow_split:
                if price_band is None:
                    return self._interleave(
                        [
                            self._fetch_batch_candidates(
                                context,
                                districts,
                                price_band=band,
                                allow_split=True,
                            )
                            for band in COLLECTION_PRICE_BANDS
                        ]
                    )
                if shapes is None and len(PROFILE_SHAPES[self.profile]) > 1:
                    return self._interleave(
                        [
                            self._fetch_batch_candidates(
                                context,
                                districts,
                                price_band=price_band,
                                shapes=(shape,),
                                allow_split=False,
                            )
                            for shape in PROFILE_SHAPES[self.profile]
                        ]
                    )
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
        self.stats = {"queries": []}
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
        queries = self.stats.get("queries", [])
        self.stats.update(
            {
                "source": "591",
                "candidate_count": len(candidates),
                "fetched": len(detailed),
                "pages_requested": self.max_pages,
                "publish_days": self.publish_days,
                "collection_max_price": self.collection_max_price,
                "query_count": len(queries),
                "truncated_queries": sum(
                    bool(item.get("truncated"))
                    for item in queries
                    if isinstance(item, dict)
                ),
                "unresolved_queries": sum(
                    bool(item.get("unresolved"))
                    for item in queries
                    if isinstance(item, dict)
                ),
            }
        )
        return detailed

    def fetch_url(self, url: str) -> HomeListing:
        parsed = urlparse(url)
        id_match = DETAIL_ID.search(parsed.path)
        if parsed.hostname != "sale.591.com.tw" or not id_match:
            raise ValueError("請貼上有效的 591 中古屋房源網址")
        canonical_url = (
            "https://sale.591.com.tw/home/house/detail/2/"
            f"{id_match.group('id')}.html"
        )
        with sync_playwright() as playwright, ExitStack() as cleanup:
            browser = self._launch(playwright)
            cleanup.callback(lambda: browser.is_connected() and browser.close())
            page = browser.new_page(locale="zh-TW")
            page.goto(canonical_url, wait_until="domcontentloaded", timeout=30000)
            page.locator("body").wait_for(timeout=15000)
            page.wait_for_timeout(1200)
            body = page.locator("body").inner_text()
            compact = re.sub(r"\s+", " ", body)
            dense = re.sub(r"\s+", "", body)
            title = page.locator("h1").first.inner_text().strip()
            price = DETAIL_PRICE.search(body)
            layout = LAYOUT.search(dense)
            floor = FLOOR.search(dense)
            district = re.search(r"高雄市\s*([^\s|>]{2,4}區)", compact)
            total_area = re.search(
                r"(?:權狀坪數|權狀)\s*([\d.]+)\s*坪", compact
            )
            age = re.search(r"屋齡\s*([\d.]+)\s*年", compact)
            if not price or not layout or not district:
                raise ValueError("591 詳情頁缺少價格、格局或行政區，無法加入")
            listing = HomeListing(
                source="591中古屋",
                external_id=id_match.group("id"),
                title=title or f"591 房源 {id_match.group('id')}",
                url=canonical_url,
                city="高雄市",
                district=district.group(1),
                total_price_wan=float(price.group("price").replace(",", "")),
                total_area_ping=float(total_area.group(1)) if total_area else None,
                rooms=float(layout.group("rooms")),
                living_rooms=float(layout.group("living")),
                baths=float(layout.group("baths")),
                age_years=float(age.group(1)) if age else None,
                current_floor=int(floor.group("current")) if floor else None,
                total_floors=int(floor.group("total")) if floor else None,
                search_profile=self.profile,
            )
            listing = parse_detail_text(listing, body)
        if listing.district not in self.districts:
            raise ValueError(
                f"房源位於 {listing.district}，不在目前搜尋行政區"
            )
        if listing.property_type not in PROFILE_TYPES[self.profile]:
            if listing.property_type == "公寓":
                raise ValueError("公寓已依目前設定直接排除")
            raise ValueError(
                f"房屋型態 {listing.property_type or '不明'} 不屬於目前目標"
            )
        if listing.total_price_wan > self.collection_max_price:
            raise ValueError(
                f"總價 {listing.total_price_wan:g} 萬，超過蒐集上限 "
                f"{self.collection_max_price:g} 萬"
            )
        return listing
