from __future__ import annotations

import json
import re
import time
from dataclasses import replace
from pathlib import Path
from typing import Callable

from playwright.sync_api import Browser, Page, sync_playwright

from .user_models import HomeListing


SECTION_IDS = {
    "楠梓區": 251,
    "三民區": 250,
    "橋頭區": 263,
    "大社區": 255,
}


def _room_count(text: str) -> float | None:
    if re.search(r"(?:二房|2房|2\+1房)", text):
        return 2
    if re.search(r"(?:三房|3房|3\+1房)", text):
        return 3
    if re.search(r"(?:四房|4房)", text):
        return 4
    return None


def _two_room_area(text: str) -> float | None:
    match = re.search(r"(?:二房|2房|2\+1房)\(([\d.]+)(?:~[\d.、]+)?坪\)", text)
    return float(match.group(1)) if match else None


def parse_presale_card(payload: dict[str, str | None]) -> HomeListing:
    href = payload.get("href") or ""
    id_match = re.search(r"newhouse\.591\.com\.tw/(?P<id>\d+)", href)
    text = payload.get("text") or ""
    address = payload.get("address") or ""
    district_match = re.search(r"高雄市(?P<district>[\u4e00-\u9fff]{1,8}區)", address)
    if not id_match or not district_match:
        raise ValueError("預售建案卡缺少 ID 或行政區")

    price_text = payload.get("price") or ""
    exact_price = re.fullmatch(r"\s*([\d,]+)\s*萬/戶\s*", price_text)
    warnings: list[str] = []
    if not exact_price:
        warnings.append(f"建案列表總價為「{price_text.strip() or '未提供'}」，需向案場確認含平車戶別總價")

    room_text = payload.get("room") or text
    total_area = _two_room_area(room_text)
    if total_area is not None:
        warnings.append(f"2 房標示 {total_area:g} 坪是銷售坪數，不是主建物坪數")

    property_type = None
    if "住宅大樓" in text:
        property_type = "電梯大樓"
    elif "華廈" in text:
        property_type = "華廈"

    return HomeListing(
        source="591預售屋",
        external_id=f"newhouse-{id_match.group('id')}",
        title=payload.get("title") or f"591 建案 {id_match.group('id')}",
        url=href,
        city="高雄市",
        district=district_match.group("district"),
        total_price_wan=float(exact_price.group(1).replace(",", "")) if exact_price else 0,
        deal_kind="預售屋",
        property_type=property_type,
        total_area_ping=total_area,
        main_area_ping=None,
        rooms=_room_count(room_text),
        age_years=0,
        address=address,
        has_parking=None,
        parking_type=None,
        data_warnings=warnings,
    )


def parse_presale_detail(listing: HomeListing, body: str) -> HomeListing:
    compact = re.sub(r"\s+", " ", body)
    parking_match = re.search(r"車位規劃\s*(.*?)\s*樓層規劃", compact)
    parking_plan = parking_match.group(1).strip() if parking_match else None
    public_ratio_match = re.search(r"公設比\s*([\d.]+)%", compact)
    warnings = list(listing.data_warnings)
    parking_type = None

    if parking_plan and "平面" in parking_plan:
        warnings.append(f"建案規劃 {parking_plan}；仍需確認目標戶別能否購買平面車位")
    elif parking_plan and "機械" in parking_plan:
        parking_type = "機械式"
    else:
        warnings.append("建案車位規劃不明")

    if listing.total_area_ping is not None and public_ratio_match:
        ratio = float(public_ratio_match.group(1)) / 100
        estimated = listing.total_area_ping * (1 - ratio)
        warnings.append(
            f"以 2 房銷售坪數與公設比粗估室內約 {estimated:.1f} 坪；含附屬建物，不能代替主建物謄本"
        )

    bath_match = re.search(r"(?:2房|2\+1房)\s*2廳\s*(\d+)衛", compact)
    return replace(
        listing,
        baths=float(bath_match.group(1)) if bath_match else listing.baths,
        parking_type=parking_type,
        has_parking=True if parking_type == "機械式" else None,
        data_warnings=warnings,
    )


class Browser591PresaleCrawler:
    def __init__(
        self,
        districts: list[str],
        max_details: int = 12,
        delay_seconds: float = 2.0,
        headless: bool = True,
        cache_path: str | Path = "data/cache/591_presale_details.json",
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not 1 <= max_details <= 30:
            raise ValueError("max_details 必須介於 1 到 30")
        if delay_seconds < 2:
            raise ValueError("delay_seconds 不可小於 2 秒")
        unknown = set(districts) - set(SECTION_IDS)
        if unknown:
            raise ValueError(f"未知行政區：{', '.join(sorted(unknown))}")
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

    def _card_payloads(self, page: Page) -> list[dict]:
        page.locator("a.card-item.list").first.wait_for(timeout=20000)
        return page.locator("a.card-item.list").evaluate_all(
            """cards => cards.map(card => ({
                text: card.innerText || '',
                href: card.href || '',
                title: (card.querySelector('.build-name .name') || {}).innerText || '',
                address: (card.querySelector('.build-address') || {}).innerText || '',
                room: (card.querySelector('.build-room') || {}).innerText || '',
                price: (card.querySelector('.price') || {}).innerText || ''
            }))"""
        )

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
        candidates: list[HomeListing] = []
        seen: set[str] = set()
        cache = self._load_cache()
        with sync_playwright() as p:
            browser = self._launch(p)
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
                    if listing.external_id not in seen and (listing.rooms or 0) >= 2:
                        seen.add(listing.external_id)
                        candidates.append(listing)

            detailed: list[HomeListing] = []
            detail_page = context.new_page()
            for index, listing in enumerate(candidates[: self.max_details]):
                cached = cache.get(listing.external_id)
                if cached:
                    detailed.append(HomeListing.from_dict(cached))
                    continue
                if index:
                    self.sleep(self.delay_seconds)
                detail_page.goto(listing.url, wait_until="domcontentloaded", timeout=30000)
                detail_page.locator("body").wait_for(timeout=15000)
                detail_page.wait_for_timeout(1500)
                item = parse_presale_detail(listing, detail_page.locator("body").inner_text())
                detailed.append(item)
                cache[item.external_id] = item.to_dict()
                self._save_cache(cache)
            browser.close()
        return detailed
