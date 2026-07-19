from __future__ import annotations

import json
import re
import time
from dataclasses import replace
from pathlib import Path
from typing import Callable
from urllib.parse import urljoin

from playwright.sync_api import Browser, Page, sync_playwright

from .user_models import HomeListing


DETAIL_ID = re.compile(r"/detail/\d+/(?P<id>\d+)\.html")
LAYOUT = re.compile(r"(?P<rooms>\d+(?:\.\d+)?)房(?P<living>\d+)廳(?P<baths>\d+)衛")
FLOOR = re.compile(r"(?P<current>\d+)F/(?P<total>\d+)F", re.I)
PRICE = re.compile(r"(?m)^\s*(?P<price>[\d,]+)\s*$\s*^\s*萬\s*$")


def _number(text: str, prefix: str, suffix: str) -> float | None:
    match = re.search(re.escape(prefix) + r"\s*([\d.]+)" + re.escape(suffix), text)
    return float(match.group(1)) if match else None


def parse_list_card(card: dict[str, str | None], city: str) -> HomeListing:
    text = card["text"] or ""
    href = card["href"] or ""
    id_match = DETAIL_ID.search(href)
    layout = LAYOUT.search(text)
    floor = FLOOR.search(text)
    price = PRICE.search(text)
    if not id_match or not layout or not price:
        raise ValueError("591 房源卡缺少 ID、格局或價格")

    age_match = re.search(r"(?m)^\s*(\d+(?:\.\d+)?)年\s*$", text)
    property_type = next(
        (name for name in ("電梯大樓", "華廈", "公寓", "透天厝", "別墅") if name in text),
        None,
    )
    tags = [name for name in ("含車位", "有陽台", "屋主刊登", "降價", "急售") if name in text]
    return HomeListing(
        source="591中古屋",
        external_id=id_match.group("id"),
        title=card["title"] or f"591 房源 {id_match.group('id')}",
        url=href,
        city=city,
        district=(card["district"] or "").rstrip("-"),
        total_price_wan=float(price.group("price").replace(",", "")),
        property_type=property_type,
        total_area_ping=_number(text, "權狀", "坪"),
        main_area_ping=_number(text, "主建", "坪"),
        rooms=float(layout.group("rooms")),
        living_rooms=float(layout.group("living")),
        baths=float(layout.group("baths")),
        age_years=float(age_match.group(1)) if age_match else None,
        current_floor=int(floor.group("current")) if floor else None,
        total_floors=int(floor.group("total")) if floor else None,
        community=card["community"],
        address=card["address"],
        has_parking=True if "含車位" in tags else None,
        tags=tags,
    )


def parse_detail_text(listing: HomeListing, body: str) -> HomeListing:
    compact = re.sub(r"\s+", " ", body)
    type_match = re.search(r"型態\s*：\s*(.*?)\s*裝潢程度", compact)
    parking_match = re.search(r"車位\s*：\s*(.*?)\s*坪數說明", compact)
    main_match = re.search(r"主建物\s*：\s*([\d.]+)坪", compact)
    warnings = list(listing.data_warnings)

    property_type = type_match.group(1).strip() if type_match else listing.property_type
    parking_raw = parking_match.group(1).strip() if parking_match else None
    if parking_raw is None:
        parking_type = listing.parking_type
        has_parking = listing.has_parking
    elif "無" == parking_raw or parking_raw.startswith("無 "):
        parking_type = "無"
        has_parking = False
    elif "平面" in parking_raw:
        parking_type = parking_raw
        has_parking = True
    elif "機械" in parking_raw:
        parking_type = parking_raw
        has_parking = True
    else:
        parking_type = parking_raw
        has_parking = True

    if "平車" in listing.title and has_parking is False:
        warnings.append("標題宣稱平車，但詳情結構化欄位顯示無車位")
    if "平車" in listing.title and parking_type and "平面" not in parking_type and parking_type != "無":
        warnings.append(f"標題宣稱平車，但詳情車位型態為 {parking_type}")
    if any(word in listing.title for word in ("車墅", "透天", "別墅")) and property_type not in {"透天厝", "別墅"}:
        warnings.append(f"標題像透天／車墅，但詳情型態為 {property_type or '不明'}")

    garden_words = ("花園", "庭院", "前院", "後院")
    has_garden = True if any(word in body for word in garden_words) else listing.has_garden
    return replace(
        listing,
        property_type=property_type,
        parking_type=parking_type,
        has_parking=has_parking,
        main_area_ping=float(main_match.group(1)) if main_match else listing.main_area_ping,
        has_garden=has_garden,
        data_warnings=warnings,
    )


class Browser591Crawler:
    def __init__(
        self,
        districts: list[str],
        max_details: int = 20,
        delay_seconds: float = 2.0,
        headless: bool = True,
        cache_path: str | Path = "data/cache/591_details.json",
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not 1 <= max_details <= 50:
            raise ValueError("max_details 必須介於 1 到 50")
        if delay_seconds < 2:
            raise ValueError("delay_seconds 不可小於 2 秒")
        self.districts = districts
        self.max_details = max_details
        self.delay_seconds = delay_seconds
        self.headless = headless
        self.cache_path = Path(cache_path)
        self.sleep = sleep

    def _launch(self, playwright) -> Browser:
        try:
            return playwright.chromium.launch(channel="chrome", headless=self.headless)
        except Exception:
            return playwright.chromium.launch(headless=self.headless)

    def _select_districts(self, page: Page) -> None:
        for district in self.districts:
            checkbox = page.get_by_role("checkbox", name=district, exact=True)
            if checkbox.count() and not checkbox.first.is_checked():
                checkbox.first.check()
                page.wait_for_timeout(500)
        page.wait_for_timeout(2500)

    def _read_cards(self, page: Page) -> list[HomeListing]:
        page.locator(".ware-item").first.wait_for(timeout=20000)
        cards = page.locator(".ware-item")
        listings: list[HomeListing] = []
        for index in range(cards.count()):
            card = cards.nth(index)
            header = card.locator(".ware-item__header a").first
            district = card.locator(".ware-item__section").first
            community = card.locator(".ware-item__community-link").first
            address = card.locator(".ware-item__address").first
            payload = {
                "text": card.inner_text(),
                "href": urljoin("https://sale.591.com.tw", header.get_attribute("href") or ""),
                "title": header.get_attribute("title") or header.inner_text(),
                "district": district.inner_text() if district.count() else None,
                "community": community.inner_text() if community.count() else None,
                "address": address.inner_text() if address.count() else None,
            }
            try:
                listing = parse_list_card(payload, "高雄市")
            except ValueError:
                continue
            if listing.district in self.districts and listing.total_price_wan <= 1200:
                listings.append(listing)
        return listings

    def _load_cache(self) -> dict[str, dict]:
        if not self.cache_path.exists():
            return {}
        try:
            return json.loads(self.cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _save_cache(self, cache: dict[str, dict]) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")

    def fetch(self) -> list[HomeListing]:
        cache = self._load_cache()
        with sync_playwright() as p:
            browser = self._launch(p)
            context = browser.new_context(
                user_agent="home-finder/0.1 personal-use low-frequency",
                locale="zh-TW",
            )
            list_page = context.new_page()
            list_page.goto(
                "https://sale.591.com.tw/?regionid=17&shType=list&firstRow=0",
                wait_until="domcontentloaded",
                timeout=30000,
            )
            self._select_districts(list_page)
            listings = self._read_cards(list_page)

            enriched: list[HomeListing] = []
            detail_page = context.new_page()
            for index, listing in enumerate(listings[: self.max_details]):
                cached = cache.get(listing.external_id)
                if cached:
                    enriched.append(HomeListing.from_dict(cached))
                    continue
                if index:
                    self.sleep(self.delay_seconds)
                detail_page.goto(listing.url, wait_until="domcontentloaded", timeout=30000)
                detail_page.locator("body").wait_for(timeout=15000)
                detail_page.wait_for_timeout(1500)
                detailed = parse_detail_text(listing, detail_page.locator("body").inner_text())
                enriched.append(detailed)
                cache[detailed.external_id] = detailed.to_dict()
                self._save_cache(cache)
            browser.close()
        return enriched
