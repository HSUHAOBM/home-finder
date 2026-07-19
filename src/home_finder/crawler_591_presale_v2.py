from __future__ import annotations

from dataclasses import replace

from . import crawler_591_presale as base
from .crawler_591_presale import Browser591PresaleCrawler as _Browser591PresaleCrawler
from .crawler_591_presale import SECTION_IDS


def parse_presale_card(payload):
    listing = base._ORIGINAL_PARSE_PRESALE_CARD(payload) if hasattr(base, "_ORIGINAL_PARSE_PRESALE_CARD") else base.parse_presale_card(payload)
    address = payload.get("address") or ""
    district = next((name for name in SECTION_IDS if f"高雄市{name}" in address), None)
    if district is None:
        raise ValueError("預售建案卡缺少目標行政區")
    return replace(listing, district=district)


class Browser591PresaleCrawler(_Browser591PresaleCrawler):
    def fetch(self):
        original = base.parse_presale_card
        base._ORIGINAL_PARSE_PRESALE_CARD = original
        base.parse_presale_card = parse_presale_card
        try:
            return super().fetch()
        finally:
            base.parse_presale_card = original
            delattr(base, "_ORIGINAL_PARSE_PRESALE_CARD")
