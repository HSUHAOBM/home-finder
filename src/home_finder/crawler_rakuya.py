from __future__ import annotations

import json
import re
import time
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlencode, urlparse

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from .user_models import HomeListing

SOURCE_NAME = "樂屋網"
BASE_URL = "https://www.rakuya.com.tw/sell/result"
DETAIL_CACHE_PATH = Path("data/cache/rakuya_details.json")
DETAIL_CACHE_TTL_SECONDS = 24 * 60 * 60
DETAIL_CACHE_SCHEMA_VERSION = 2
DETAIL_PARSER_VERSION = 2
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


def _line_after(body_text: str, heading: str) -> str | None:
    lines = [line.strip() for line in body_text.splitlines() if line.strip()]
    for index, line in enumerate(lines):
        if line != heading:
            continue
        for value in lines[index + 1:index + 5]:
            if value != heading:
                return value
    return None


def parse_rakuya_detail_text(listing: HomeListing, body_text: str) -> HomeListing:
    type_value = _line_after(body_text, "類型")
    property_type = _property_type(type_value or "") or listing.property_type
    main_area = _line_after(body_text, "主建物")
    parking_value = _line_after(body_text, "車位")
    parking_type = _line_after(body_text, "車位類型")
    address_match = re.search(
        r"高雄市(?P<district>三民區|左營區|楠梓區|橋頭區|仁武區|大社區)"
        r"(?P<address>[^\s\n]+)",
        body_text,
    )
    brand_match = re.search(
        r"^(?P<brand>(?:永慶不動產|永義房屋|台慶不動產|住商不動產|"
        r"中信房屋|大家房屋|東森房屋|信義房屋|太平洋房屋|"
        r"21世紀不動產|全國不動產)[^\n]*)$",
        body_text,
        re.MULTILINE,
    )
    company_match = re.search(
        r"^(?P<company>[^\n]{2,60}(?:不動產|房屋|地產)[^\n]{0,30}"
        r"(?:有限公司|股份有限公司))$",
        body_text,
        re.MULTILINE,
    )
    warnings = [
        warning for warning in listing.data_warnings
        if "尚未讀取詳情確認車位型式" not in warning
    ]
    list_claimed_flat = any(
        value in warning
        for warning in listing.data_warnings
        for value in ("平面車位", "平車")
    )
    if parking_type and list_claimed_flat and "機械" in parking_type:
        warnings.append(f"樂屋列表宣稱平面車位，但詳情欄位為：{parking_type}")
    if not parking_type:
        warnings.append("樂屋詳情頁未提供車位類型")

    has_parking: bool | None
    if parking_value:
        has_parking = "無" not in parking_value
    elif parking_type:
        has_parking = "無" not in parking_type
    else:
        has_parking = listing.has_parking

    return replace(
        listing,
        district=address_match.group("district") if address_match else listing.district,
        address=(
            f"高雄市{address_match.group('district')}{address_match.group('address')}"
            if address_match else listing.address
        ),
        property_type=property_type,
        main_area_ping=(
            _float(main_area.removesuffix("坪"))
            if main_area and re.fullmatch(r"[\d.]+\s*坪", main_area)
            else listing.main_area_ping
        ),
        parking_type=parking_type or listing.parking_type,
        has_parking=has_parking,
        origin_source=brand_match.group("brand") if brand_match else listing.origin_source,
        broker_name=company_match.group("company") if company_match else listing.broker_name,
        data_warnings=warnings,
    )


class BrowserRakuyaPilotCrawler:
    def __init__(
        self, districts: list[str], max_price: float, max_pages: int = 3,
        delay_seconds: float = 3.0, headless: bool = False, background: bool = True,
        balanced_districts: bool = False,
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
        self.background = background
        self.balanced_districts = balanced_districts
        self.headless = headless
        self.sleep = sleep
        self.stats: dict[str, Any] = {}
        self.detail_stats: dict[str, Any] = {}


    def _launch_options(self) -> dict[str, Any]:
        options: dict[str, Any] = {"headless": self.headless}
        if self.background and not self.headless:
            options["args"] = [
                "--window-position=-32000,-32000",
                "--window-size=1280,900",
            ]
        return options


    def _list_url(
        self, page_number: int, districts: list[str] | None = None
    ) -> str:
        selected_districts = districts or self.districts
        query = {
            "zipcode": ",".join(
                DISTRICT_ZIPCODES[value] for value in selected_districts
            ),
            "agetype": "O", "price": f"0~{self.max_price:g}", "typecode": "R1,R2",
        }
        if page_number > 1:
            query["page"] = str(page_number)
        return f"{BASE_URL}?{urlencode(query)}"

    def _request_plan(self) -> list[tuple[list[str], int]]:
        if self.balanced_districts:
            return [([district], 1) for district in self.districts]
        return [
            (self.districts, page_number)
            for page_number in range(1, self.max_pages + 1)
        ]

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
        request_plan = self._request_plan()
        request_details: list[dict[str, Any]] = []
        district_counts = {district: 0 for district in self.districts}
        with sync_playwright() as playwright:
            state_path = Path("data/cache/rakuya_storage_state.json").resolve()
            try:
                browser = playwright.chromium.launch(channel="chrome", **self._launch_options())
            except Exception:
                browser = playwright.chromium.launch(**self._launch_options())
            context_options: dict[str, Any] = {"locale": "zh-TW"}
            if state_path.exists():
                context_options["storage_state"] = str(state_path)
            context = browser.new_context(**context_options)
            try:
                page = context.new_page()
                for request_index, request in enumerate(request_plan):
                    request_districts, page_number = request
                    if request_index:
                        self.sleep(self.delay_seconds)
                    page.goto(
                        self._list_url(page_number, request_districts),
                        wait_until="domcontentloaded",
                        timeout=30000,
                    )
                    page.wait_for_timeout(4000)
                    page_listings, current_total = self._read_page(page)
                    request_detail: dict[str, Any] = {
                        "districts": request_districts,
                        "page_number": page_number,
                    }
                    if current_total is not None:
                        request_detail["reported_total"] = current_total
                    if result_total is None:
                        result_total = current_total
                    added = 0
                    for listing in page_listings:
                        if listing.external_id in seen:
                            continue
                        seen.add(listing.external_id)
                        fetched.append(listing)
                        added += 1
                        district_counts[listing.district] += 1
                    page_counts.append(added)
                    request_detail["unique_added"] = added
                    request_details.append(request_detail)
                context.storage_state(path=str(state_path))
            finally:
                context.close()
                browser.close()
        district_totals = {
            item["districts"][0]: item["reported_total"]
            for item in request_details
            if len(item["districts"]) == 1
            and item.get("reported_total") is not None
        }
        if self.balanced_districts and district_totals:
            result_total = sum(district_totals.values())
        self.stats = {
            "source": SOURCE_NAME, "pages_requested": len(request_plan),
            "configured_combined_pages": self.max_pages,
            "sampling_mode": (
                "one_page_per_district" if self.balanced_districts else "combined"
            ),
            "page_unique_counts": page_counts, "fetched": len(fetched),
            "request_details": request_details,
            "district_unique_counts": district_counts,
            "district_reported_totals": district_totals,
            "reported_total": result_total,
            "headless": self.headless,
            "background": self.background,
            "duration_seconds": round(time.time() - started, 1),
        }
        return fetched

    @staticmethod
    def _load_detail_cache(cache_path: Path) -> dict[str, Any]:
        if not cache_path.exists():
            return {"schema_version": DETAIL_CACHE_SCHEMA_VERSION, "entries": {}}
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("樂屋詳情快取格式錯誤；原檔已保留")

        if payload.get("schema_version") == DETAIL_CACHE_SCHEMA_VERSION:
            entries = payload.get("entries")
            if not isinstance(entries, dict):
                raise ValueError("樂屋詳情快取 entries 格式錯誤；原檔已保留")
            return payload

        if all(isinstance(value, dict) for value in payload.values()):
            legacy_time = cache_path.stat().st_mtime
            return {
                "schema_version": DETAIL_CACHE_SCHEMA_VERSION,
                "entries": {
                    external_id: {
                        "fetched_at": legacy_time,
                        "parser_version": 1,
                        "listing": listing,
                    }
                    for external_id, listing in payload.items()
                },
            }
        raise ValueError("樂屋詳情快取格式錯誤；原檔已保留")

    @staticmethod
    def _cached_detail(
        payload: dict[str, Any], external_id: str, *, now: float | None = None
    ) -> dict[str, Any] | None:
        entry = payload.get("entries", {}).get(external_id)
        if not isinstance(entry, dict):
            return None
        fetched_at = entry.get("fetched_at")
        listing = entry.get("listing")
        if (
            entry.get("parser_version") != DETAIL_PARSER_VERSION
            or not isinstance(fetched_at, (int, float))
            or not isinstance(listing, dict)
        ):
            return None
        age = (time.time() if now is None else now) - float(fetched_at)
        if age < 0 or age >= DETAIL_CACHE_TTL_SECONDS:
            return None
        return listing

    @staticmethod
    def _store_cached_detail(
        payload: dict[str, Any], detail: HomeListing, *, fetched_at: float | None = None
    ) -> None:
        payload.setdefault("entries", {})[detail.external_id] = {
            "fetched_at": time.time() if fetched_at is None else fetched_at,
            "parser_version": DETAIL_PARSER_VERSION,
            "listing": detail.to_dict(),
        }

    @staticmethod
    def _save_detail_cache(
        cache_path: Path, payload: dict[str, Any]
    ) -> None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = cache_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temporary.replace(cache_path)

    def enrich_details(
        self,
        listings: list[HomeListing],
        *,
        max_details: int = 15,
        cache_path: str | Path = DETAIL_CACHE_PATH,
    ) -> list[HomeListing]:
        if not 1 <= max_details <= 15:
            raise ValueError("樂屋詳情試爬 max_details 必須介於 1 到 15")
        started = time.time()
        path = Path(cache_path)
        cache = self._load_detail_cache(path)
        selected = listings[:max_details]
        results: list[HomeListing] = []
        cached_payloads = {
            item.external_id: self._cached_detail(cache, item.external_id)
            for item in selected
        }
        uncached = [
            item for item in selected if cached_payloads[item.external_id] is None
        ]
        cache_hits = len(selected) - len(uncached)
        failures = 0

        for listing in selected:
            cached = cached_payloads[listing.external_id]
            if cached:
                detail = HomeListing.from_dict(cached)
                if detail.broker_name and not any(
                    term in detail.broker_name
                    for term in ("不動產", "房屋", "地產")
                ):
                    detail = replace(detail, broker_name=None)
                results.append(replace(
                    detail,
                    title=listing.title,
                    url=listing.url,
                    total_price_wan=listing.total_price_wan,
                    search_profile=listing.search_profile,
                ))

        if uncached:
            with sync_playwright() as playwright:
                state_path = Path("data/cache/rakuya_storage_state.json").resolve()
                try:
                    browser = playwright.chromium.launch(
                        channel="chrome", **self._launch_options()
                    )
                except Exception:
                    browser = playwright.chromium.launch(**self._launch_options())
                context_options: dict[str, Any] = {"locale": "zh-TW"}
                if state_path.exists():
                    context_options["storage_state"] = str(state_path)
                context = browser.new_context(**context_options)
                try:
                    page = context.new_page()
                    for index, listing in enumerate(uncached):
                        if index:
                            self.sleep(self.delay_seconds)
                        try:
                            page.goto(
                                listing.url,
                                wait_until="domcontentloaded",
                                timeout=30000,
                            )
                            page.locator("body").wait_for(timeout=15000)
                            page.wait_for_timeout(3000)
                            challenge = self._challenge_message(page)
                            if challenge:
                                raise RuntimeError(challenge)
                            detail = parse_rakuya_detail_text(
                                listing, page.locator("body").inner_text()
                            )
                        except Exception as exc:
                            failures += 1
                            detail = replace(
                                listing,
                                data_warnings=listing.data_warnings + [
                                    f"樂屋詳情頁讀取失敗：{type(exc).__name__}"
                                ],
                            )
                            results.append(detail)
                            continue
                        self._store_cached_detail(cache, detail)
                        self._save_detail_cache(path, cache)
                        results.append(detail)
                    context.storage_state(path=str(state_path))
                finally:
                    context.close()
                    browser.close()

        order = {item.external_id: index for index, item in enumerate(selected)}
        results.sort(key=lambda item: order[item.external_id])
        self.detail_stats = {
            "requested": len(selected),
            "cache_hits": cache_hits,
            "network_requests": len(uncached),
            "failures": failures,
            "duration_seconds": round(time.time() - started, 1),
        }
        return results
