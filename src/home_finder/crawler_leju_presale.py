from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urljoin

from playwright.sync_api import Browser, sync_playwright

from .user_models import HomeListing


SOURCE_NAME = "樂居新建案"
BASE_URL = "https://www.leju.com.tw"
DISTRICT_POST_CODES = {
    "三民區": "807",
    "楠梓區": "811",
    "小港區": "812",
    "左營區": "813",
    "仁武區": "814",
    "大社區": "815",
    "岡山區": "820",
    "路竹區": "821",
    "阿蓮區": "822",
    "田寮區": "823",
    "燕巢區": "824",
    "橋頭區": "825",
    "梓官區": "826",
    "彌陀區": "827",
    "永安區": "828",
    "湖內區": "829",
    "鳳山區": "830",
    "大寮區": "831",
    "林園區": "832",
    "鳥松區": "833",
    "大樹區": "840",
    "旗山區": "842",
    "美濃區": "843",
    "六龜區": "844",
    "內門區": "845",
    "杉林區": "846",
    "甲仙區": "847",
    "桃源區": "848",
    "那瑪夏區": "849",
    "茂林區": "851",
    "新興區": "800",
    "前金區": "801",
    "苓雅區": "802",
    "鹽埕區": "803",
    "鼓山區": "804",
    "旗津區": "805",
    "前鎮區": "806",
}


def _number(pattern: str, text: str) -> float | None:
    match = re.search(pattern, text)
    return float(match.group(1)) if match else None


def parse_leju_card(payload: dict[str, str], district: str) -> HomeListing:
    href = payload.get("href", "")
    id_match = re.search(r"/community/(?P<id>L[0-9a-z]+)", href, re.I)
    title = re.sub(r"\s*[↗]\s*$", "", payload.get("title", "")).strip()
    text = re.sub(r"\s+", " ", payload.get("text", "")).strip()
    if not id_match or not title:
        raise ValueError("樂居建案卡缺少識別碼或名稱")

    two_room = re.search(r"2房\s*(?!-{2})([\d.]+)(?:~([\d.]+))?\s*坪", text)
    rooms = 2.0 if two_room else None
    total_area = float(two_room.group(1)) if two_room else None
    public_ratio = _number(r"公設比\s*([\d.]+)%", text)
    total_units = _number(r"總戶數\s*([\d.]+)\s*戶", text)
    age = _number(r"屋齡\s*([\d.]+)\s*年", text)
    asking = re.search(r"開價\s*([\d.]+)(?:~([\d.]+))?萬\s*/坪", text)
    warnings = ["樂居新建案清單可能同時包含預售屋與近期完工新成屋，交易型態需確認"]
    if asking:
        high = asking.group(2) or asking.group(1)
        warnings.append(f"樂居公開開價約 {asking.group(1)}～{high} 萬／坪，不是含車位戶別總價")
    else:
        warnings.append("樂居總價與每坪開價尚未公開，需向案場確認")
    if total_area is not None:
        warnings.append(f"樂居 2 房標示 {total_area:g} 坪起，屬銷售坪數，不是主建物坪數")
    if public_ratio is not None:
        warnings.append(f"樂居公開公設比 {public_ratio:g}%，仍應以契約及戶別面積表確認")
    if total_units is not None:
        warnings.append(f"樂居公開總戶數 {total_units:g} 戶")
    if "充電車位" in text:
        warnings.append("樂居標示社區具有充電車位資訊，但目標戶別的車位型式仍待確認")

    return HomeListing(
        source=SOURCE_NAME,
        external_id=id_match.group("id"),
        title=title,
        url=urljoin(BASE_URL, href),
        city="高雄市",
        district=district,
        total_price_wan=0,
        deal_kind="預售屋",
        property_type="電梯大樓",
        total_area_ping=total_area,
        main_area_ping=None,
        rooms=rooms,
        age_years=age,
        address=payload.get("address") or None,
        parking_type=None,
        has_parking=None,
        data_warnings=warnings,
        search_profile="預售屋",
    )


class BrowserLejuPresaleCrawler:
    def __init__(
        self,
        districts: list[str],
        max_projects: int = 80,
        delay_seconds: float = 2.0,
        headless: bool = False,
        background: bool = True,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not 1 <= max_projects <= 300:
            raise ValueError("樂居建案上限必須介於 1 到 300")
        self.districts = [item for item in districts if item in DISTRICT_POST_CODES]
        self.max_projects = max_projects
        self.delay_seconds = max(2.0, delay_seconds)
        self.headless = headless
        self.background = background
        self.sleep = sleep
        self.cache_expired = False
        self.stats: dict[str, Any] = {}

    def _launch(self, playwright) -> Browser:
        options: dict[str, Any] = {"headless": self.headless}
        if self.background and not self.headless:
            options["args"] = [
                "--window-position=-32000,-32000",
                "--window-size=1280,900",
            ]
        try:
            return playwright.chromium.launch(channel="chrome", **options)
        except Exception:
            return playwright.chromium.launch(**options)

    def fetch(self) -> list[HomeListing]:
        listings: list[HomeListing] = []
        seen: set[str] = set()
        district_counts: dict[str, int] = {}
        with sync_playwright() as playwright:
            browser = self._launch(playwright)
            try:
                page = browser.new_page(locale="zh-TW")
                for index, district in enumerate(self.districts):
                    if len(listings) >= self.max_projects:
                        break
                    if index:
                        self.sleep(self.delay_seconds)
                    post_code = DISTRICT_POST_CODES[district]
                    page.goto(
                        f"{BASE_URL}/community_list?area=E{post_code}&city=E&is_new=1",
                        wait_until="domcontentloaded",
                        timeout=30000,
                    )
                    page.wait_for_timeout(3500)
                    page.locator('a[href*="/community/L"]').first.wait_for(timeout=20000)
                    payloads = page.locator("body").evaluate(
                        """body => {
                          const links = [...body.querySelectorAll('a[href*="/community/L"]')];
                          const hrefs = [...new Set(links.map(link => link.getAttribute('href')).filter(Boolean))];
                          return hrefs.map(href => {
                            const sameLinks = links.filter(link => link.getAttribute('href') === href);
                            const titleLink = sameLinks.find(link => !link.innerText.includes('前往看更多')) || sameLinks[0];
                            const detailLink = sameLinks.find(link => link.innerText.includes('前往看更多')) || sameLinks.at(-1);
                            const card = titleLink?.closest('section') || detailLink?.closest('section');
                            const locationIcon = card?.querySelector('[class*="icon-location"]');
                            return {
                              href,
                              title: card?.querySelector('h5')?.innerText || titleLink?.innerText || '',
                              address: card?.querySelector('address')?.innerText || locationIcon?.parentElement?.innerText || '',
                              text: card?.innerText || ''
                            };
                          }).filter(item => item.text && item.title);
                        }"""
                    )
                    added = 0
                    for payload in payloads:
                        try:
                            listing = parse_leju_card(payload, district)
                        except ValueError:
                            continue
                        if listing.external_id in seen:
                            continue
                        seen.add(listing.external_id)
                        listings.append(listing)
                        added += 1
                        if len(listings) >= self.max_projects:
                            break
                    district_counts[district] = added
            finally:
                browser.close()
        self.stats = {
            "source": SOURCE_NAME,
            "fetched": len(listings),
            "district_counts": district_counts,
            "list_pages": len(district_counts),
            "coverage_note": "每區目前讀取樂居新建案清單首批，作為 591 補漏；未知總價仍保留",
        }
        return listings
