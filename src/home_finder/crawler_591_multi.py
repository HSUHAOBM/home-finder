from __future__ import annotations

import re
import json
from datetime import datetime, timezone
from functools import wraps
from uuid import uuid4
from contextlib import ExitStack
from dataclasses import replace
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

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
from .kaohsiung_districts import SECTION_IDS


PROFILE_SHAPES = {
    "大樓公寓華廈": ("電梯大樓", "華廈"),
    "透天別墅": ("透天厝", "別墅"),
}
PROFILE_TYPES = {
    "大樓公寓華廈": {"電梯大樓", "華廈"},
    "透天別墅": {"透天厝", "別墅"},
}
SHAPE_IDS = {"電梯大樓": "2", "華廈": "5", "透天厝": "3", "別墅": "4"}
UPDATE_TEXT = re.compile(r"(?:剛剛|\d+\s*(?:分鐘|小時|天)前|今天|昨日|昨天)\s*更新")
DETAIL_AGE = re.compile(r"屋齡\s*([\d.]+)\s*年|([\d.]+)\s*年\s*屋齡")
COLLECTION_PRICE_BANDS = ("0_500", "500_750", "750_1000", "1000_1250", "1250_1500")


def traced_crawl(method):
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        self._run_id = uuid4().hex
        self._audit("run_started", operation=method.__name__, districts=self.districts,
                    max_pages=self.max_pages, publish_days=self.publish_days,
                    max_details=self.max_details, collection_max_price=self.collection_max_price,
                    requested_url=args[0] if args else None)
        try:
            result = method(self, *args, **kwargs)
        except Exception as exc:
            self._audit("run_failed", error_type=type(exc).__name__, error=str(exc))
            raise
        self._audit("run_finished", count=len(result) if isinstance(result, list) else 1,
                    stats=self.stats)
        return result
    return wrapped


class MultiPage591ResaleCrawler(Browser591Crawler):
    def __init__(
        self,
        profile: str,
        districts: list[str],
        max_pages: int = 3,
        publish_days: int = 3,
        max_details: int | None = 50,
        collection_max_price: float = 1300,
        audit_path: str | Path | None = None,
        **kwargs,
    ) -> None:
        super().__init__(districts=districts, max_details=max_details, **kwargs)
        if profile not in PROFILE_SHAPES:
            raise ValueError(f"不支援的中古屋目標：{profile}")
        if not 3 <= max_pages <= 15:
            raise ValueError("max_pages 必須介於 3 到 15")
        if publish_days not in {0, 1, 3, 5, 7, 10, 15, 30}:
            raise ValueError("publish_days 不支援")
        self.profile = profile
        self.max_pages = max_pages
        self.publish_days = publish_days
        self.collection_max_price = float(collection_max_price)
        if self.collection_max_price <= 0:
            raise ValueError("collection_max_price 必須大於 0")
        self.stats: dict[str, object] = {}
        self.audit_path = Path(audit_path) if audit_path is not None else (
            Path(__file__).resolve().parents[2] / "data" / "crawler_591_trace.jsonl"
        )
        self._run_id = uuid4().hex

    def _audit(self, event: str, **fields) -> None:
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        record = {"timestamp": datetime.now(timezone.utc).isoformat(),
                  "run_id": self._run_id, "source": "591", "profile": self.profile,
                  "event": event, **fields}
        with self.audit_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _select_shapes(self, page: Page, shapes: tuple[str, ...] | None = None) -> None:
        for shape in shapes or PROFILE_SHAPES[self.profile]:
            label = page.locator("label").filter(has_text=re.compile(rf"^\s*{re.escape(shape)}\s*$"))
            if label.count():
                label.first.click()
                page.wait_for_timeout(700)
        page.wait_for_timeout(2500)

    def _read_profile_cards(self, page: Page) -> list[HomeListing]:
        self._page_read_failed = False
        try:
            page.locator(".ware-item").first.wait_for(timeout=8000)
        except PlaywrightTimeoutError:
            self._audit("page_cards_timeout", url=page.url)
            self._page_read_failed = True
            return []
        payloads = page.locator(".ware-item").evaluate_all(
            """cards => cards.map(card => {
                const header = card.querySelector('.ware-item__header a')
                    || card.querySelector('a[href*="/home/house/detail/"]');
                const district = card.querySelector('.ware-item__section');
                const community = card.querySelector('.ware-item__community-link');
                const address = card.querySelector('.ware-item__address');
                const price = card.querySelector('.ware-item__price-value');
                return {
                    text: card.innerText || '', href: header ? header.href : '',
                    recommendation: !card.querySelector('.ware-item__attrs'),
                    external_id: card.getAttribute('data-id'),
                    price_wan: price ? price.textContent.trim() : null,
                    title: header ? (header.getAttribute('title') || header.innerText) : '',
                    district: district ? district.innerText : '',
                    community: community ? community.innerText : null,
                    address: address ? address.innerText : null
                };
            })"""
        )
        listings: list[HomeListing] = []
        self._audit("page_cards_read", url=page.url, raw_count=len(payloads))
        for payload in payloads:
            if payload.get("recommendation"):
                self._audit("recommendation_skipped", card=payload)
                continue
            if not payload.get("href") and str(payload.get("external_id") or "").isdigit():
                payload["href"] = (
                    "https://sale.591.com.tw/home/house/detail/2/"
                    + str(payload["external_id"]) + ".html"
                )
            payload["href"] = urljoin("https://sale.591.com.tw", payload.get("href") or "")
            try:
                listing = parse_list_card(payload, "高雄市")
            except ValueError as exc:
                self._page_read_failed = True
                id_match = DETAIL_ID.search(payload["href"])
                self._audit("card_parse_failed", url=payload["href"],
                            external_id=id_match.group("id") if id_match else None,
                            error=str(exc), card=payload)
                continue
            updated = UPDATE_TEXT.search(payload.get("text") or "")
            listing = replace(
                listing,
                search_profile=self.profile,
                listing_updated_text=updated.group(0) if updated else None,
            )
            reasons = []
            if listing.district not in self.districts:
                reasons.append("district_not_selected")
            if listing.total_price_wan > self.collection_max_price:
                reasons.append("price_over_limit")
            if listing.property_type not in PROFILE_TYPES[self.profile]:
                reasons.append("property_type_not_selected")
            self._audit("card_rejected" if reasons else "card_accepted",
                        external_id=listing.external_id, url=listing.url,
                        reasons=reasons, listing=listing.to_dict(), card=payload)
            if not reasons:
                listings.append(listing)
        return listings

    def _query_parameters(self, districts, shapes=None, price_band=None) -> dict:
        unknown = [district for district in districts if district not in SECTION_IDS]
        if unknown:
            raise ValueError("591 行政區代碼未設定：" + "、".join(unknown))
        query = {"regionid": "17", "section": ",".join(str(SECTION_IDS[d]) for d in districts),
                 "shape": ",".join(SHAPE_IDS[s] for s in shapes or PROFILE_SHAPES[self.profile]),
                 "firstRow": "0", "shType": "list"}
        if self.publish_days:
            query["publish_day"] = str(self.publish_days)
        if price_band:
            query["price"] = price_band
        return query

    @staticmethod
    def _filters_match(url: str, expected: dict) -> bool:
        actual = parse_qs(urlparse(url).query)
        return all(actual.get(key) == [str(value)] for key, value in expected.items()
                   if key not in {"firstRow", "shType"})

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
            query = self._query_parameters(districts, shapes, price_band)
            list_page.goto(
                "https://sale.591.com.tw/?" + urlencode(query),
                wait_until="domcontentloaded",
                timeout=30000,
            )
            list_page.wait_for_timeout(2500)
            self._audit("query_started", url=list_page.url, districts=districts,
                        price_band=price_band, shapes=list(shapes or PROFILE_SHAPES[self.profile]))

            candidates: list[HomeListing] = []
            seen: set[str] = set()
            pages_scanned = 0
            incomplete_reason = None
            for page_number in range(1, self.max_pages + 1):
                if page_number > 1:
                    next_link = list_page.get_by_role("link", name="下一頁", exact=True)
                    if not next_link.count():
                        self._audit("pagination_stopped", url=list_page.url,
                                    page_number=page_number - 1, reason="next_link_missing")
                        break
                    self.sleep(self.delay_seconds)
                    before = list_page.locator('.ware-item__header a').evaluate_all(
                        "links => links.map(link => link.href).join('|')"
                    )
                    try:
                        page_query = {**query, "page": str(page_number),
                                      "firstRow": str((page_number - 1) * 30)}
                        list_page.goto("https://sale.591.com.tw/?" + urlencode(page_query),
                                       wait_until="domcontentloaded", timeout=30000)
                        list_page.wait_for_function(
                            "previous => { const links = Array.from(document.querySelectorAll('.ware-item__header a'));"
                            " return links.length > 0 && links.map(link => link.href).join('|') !== previous; }",
                            arg=before, timeout=15000,
                        )
                        list_page.wait_for_timeout(700)
                    except PlaywrightTimeoutError:
                        incomplete_reason = "pagination_timeout_or_repeated_page"
                        self._audit("pagination_stopped", url=list_page.url,
                                    page_number=page_number, reason=incomplete_reason)
                        break
                if not self._filters_match(list_page.url, query):
                    incomplete_reason = "filters_lost"
                    self._audit("pagination_stopped", url=list_page.url,
                                page_number=page_number, reason=incomplete_reason, expected=query)
                    break
                page_listings = self._read_profile_cards(list_page)
                if self._page_read_failed:
                    incomplete_reason = "cards_timeout_or_parse_failed"
                if self._page_read_failed and not page_listings:
                    break
                self._audit("page_candidates", url=list_page.url,
                            page_number=page_number, count=len(page_listings))
                pages_scanned = page_number
                for listing in page_listings:
                    if listing.external_id not in seen:
                        seen.add(listing.external_id)
                        candidates.append(listing)
                    else:
                        self._audit("duplicate_card_skipped", external_id=listing.external_id,
                                    url=listing.url)
            next_link = list_page.get_by_role("link", name="下一頁", exact=True)
            next_href = (
                next_link.first.get_attribute("href") or ""
                if next_link.count()
                else ""
            )
            truncated = bool(next_href and pages_scanned >= self.max_pages)
            self._audit("query_finished", districts=districts, price_band=price_band,
                        pages_scanned=pages_scanned, candidates=len(candidates),
                        next_href=next_href, truncated=truncated, allow_split=allow_split,
                        incomplete_reason=incomplete_reason)
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
                        "unresolved": bool(incomplete_reason or (truncated and not allow_split)),
                        "incomplete_reason": incomplete_reason,
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
        except PlaywrightTimeoutError as exc:
            self._audit("query_failed", districts=districts, error=str(exc),
                        error_type=type(exc).__name__)
            self.stats.setdefault("queries", []).append({
                "districts": list(districts), "price_band": price_band,
                "pages_scanned": locals().get("pages_scanned", 0),
                "candidates": len(locals().get("candidates", [])),
                "truncated": False, "unresolved": True,
                "incomplete_reason": "query_timeout",
            })
            return locals().get("candidates", [])
        finally:
            self.districts = original_districts
            list_page.close()

    def _collect_candidates(self, context: BrowserContext) -> list[HomeListing]:
        batch_candidates: list[list[HomeListing]] = []
        empty_batch_retries: list[str] = []
        for districts in self._district_batches():
            batch = self._fetch_batch_candidates(context, districts)
            if not batch and self.publish_days == 0:
                district = districts[0]
                empty_batch_retries.append(district)
                self._audit("empty_batch_retry", district=district)
                self.sleep(self.delay_seconds)
                batch = self._fetch_batch_candidates(context, districts)
            batch_candidates.append(batch)
        self.stats["empty_batch_retries"] = empty_batch_retries
        self.stats["empty_batch_retry_count"] = len(empty_batch_retries)
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

    @traced_crawl
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
            deferred_details = 0
            for listing in candidates:
                cached_data = cache.get(listing.external_id)
                # A failed detail or a parking tag without its type is not a
                # completed verification and must not permanently block retries.
                if cached_data and not (
                    cached_data.get("lifecycle_status") == "possibly_removed"
                    or not cached_data.get("parking_type")
                    or any("車位資料矛盾" in warning
                           for warning in cached_data.get("data_warnings", []))
                ):
                    self._audit("detail_cache_hit", external_id=listing.external_id,
                                cache_path=str(self.cache_path) if hasattr(self, "cache_path") else None)
                    detailed.append(self._merge_cached(listing, HomeListing.from_dict(cached_data)))
                    continue
                if (
                    self.max_details is not None
                    and uncached_requests >= self.max_details
                    and not (listing.has_parking is True and not listing.parking_type)
                ):
                    deferred_details += 1
                    self._audit("detail_deferred", external_id=listing.external_id,
                                reason="detail_limit", limit=self.max_details)
                    detailed.append(
                        replace(
                            listing,
                            data_warnings=listing.data_warnings + [
                                f"本輪尚未讀取詳情：已達 {self.max_details} 筆詳情頁上限"
                            ],
                        )
                    )
                    continue
                if uncached_requests:
                    self.sleep(self.delay_seconds)
                uncached_requests += 1
                self._audit("detail_started", external_id=listing.external_id, url=listing.url)
                try:
                    detail_page.goto(listing.url, wait_until="domcontentloaded", timeout=30000)
                    detail_page.locator("body").wait_for(timeout=15000)
                    detail_page.wait_for_timeout(1200)
                    item = parse_detail_text(listing, detail_page.locator("body").inner_text())
                    self._audit("detail_parsed", external_id=listing.external_id,
                                listing=item.to_dict())
                except Exception as exc:
                    self._audit("detail_failed", external_id=listing.external_id,
                                url=listing.url, error_type=type(exc).__name__, error=str(exc))
                    item = replace(
                        listing,
                        lifecycle_status="possibly_removed",
                        data_warnings=listing.data_warnings + [f"詳情頁讀取失敗：{type(exc).__name__}"],
                    )
                detailed.append(item)
                if item.lifecycle_status != "possibly_removed":
                    cache[item.external_id] = item.to_dict()
                    self._save_cache(cache)
            browser.close()
        queries = self.stats.get("queries", [])
        self.stats.update(
            {
                "source": "591",
                "candidate_count": len(candidates),
                "fetched": len(detailed),
                "detail_requests": uncached_requests,
                "detail_deferred": deferred_details,
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

    @traced_crawl
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
            age = DETAIL_AGE.search(compact)
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
                age_years=float(age.group(1) or age.group(2)) if age else None,
                current_floor=int(floor.group("current")) if floor else None,
                total_floors=int(floor.group("total")) if floor else None,
                search_profile=self.profile,
            )
            listing = parse_detail_text(listing, body)
            self._audit("direct_detail_parsed", external_id=listing.external_id,
                        url=canonical_url, listing=listing.to_dict())
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
