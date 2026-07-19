from __future__ import annotations

from urllib.parse import urljoin

from playwright.sync_api import Page

from .crawler_591_browser import parse_list_card
from .crawler_591_browser_v2 import Browser591Crawler as _Browser591Crawler
from .user_models import HomeListing


class Browser591Crawler(_Browser591Crawler):
    """591 crawler using an atomic DOM snapshot for dynamic result cards."""

    def _read_cards(self, page: Page) -> list[HomeListing]:
        page.locator(".ware-item").first.wait_for(timeout=20000)
        payloads = page.locator(".ware-item").evaluate_all(
            """cards => cards.map(card => {
                const header = card.querySelector('.ware-item__header a');
                const district = card.querySelector('.ware-item__section');
                const community = card.querySelector('.ware-item__community-link');
                const address = card.querySelector('.ware-item__address');
                return {
                    text: card.innerText || '',
                    href: header ? header.href : '',
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
            if listing.district in self.districts and listing.total_price_wan <= 1200:
                listings.append(listing)
        return listings
