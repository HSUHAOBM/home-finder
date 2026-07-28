from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .crawler_rakuya import BrowserRakuyaPilotCrawler, SOURCE_NAME
from .user_models import HomeListing
from .user_ranking import duplicate_key

DEFAULT_CONFIG = Path("config.user.json")
DEFAULT_CURRENT_RESULTS = Path("output/current-results.json")
DEFAULT_REPORT = Path("output/rakuya-pilot.json")


def _load_current_listings(path: Path) -> list[HomeListing]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    listings: list[HomeListing] = []
    seen: set[tuple[str, str]] = set()
    for record in payload.get("records", []):
        data = record.get("listing")
        if not isinstance(data, dict):
            continue
        listing = HomeListing.from_dict(data)
        key = (listing.source, listing.external_id)
        if key in seen:
            continue
        seen.add(key)
        listings.append(listing)
    return listings


def compare_with_current(pilot: list[HomeListing], current: list[HomeListing]) -> dict[str, Any]:
    current_keys: dict[tuple, list[HomeListing]] = {}
    for listing in current:
        key = duplicate_key(listing)
        if key is not None:
            current_keys.setdefault(key, []).append(listing)

    overlaps: list[dict[str, Any]] = []
    potential_new: list[HomeListing] = []
    for listing in pilot:
        key = duplicate_key(listing)
        matched = current_keys.get(key, []) if key is not None else []
        if matched:
            overlaps.append({
                "rakuya": listing.to_dict(),
                "matches": [{
                    "source": item.source, "external_id": item.external_id,
                    "title": item.title, "url": item.url,
                } for item in matched],
            })
        else:
            potential_new.append(listing)

    return {
        "current_listing_count": len(current),
        "current_sources": dict(Counter(item.source for item in current)),
        "overlap_count": len(overlaps),
        "potential_new_count": len(potential_new),
        "overlap_rate": round(len(overlaps) / len(pilot), 4) if pilot else 0,
        "overlaps": overlaps,
        "potential_new": [item.to_dict() for item in potential_new],
        "note": "僅以行政區、社區/地址、坪數、房數、樓層的保守規則比對；未命中不代表一定是新房。",
    }


def run_pilot(
    config_path: Path = DEFAULT_CONFIG,
    current_results_path: Path = DEFAULT_CURRENT_RESULTS,
    report_path: Path = DEFAULT_REPORT,
    *, max_pages: int = 3, headless: bool = False,
) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    settings = config["editable_criteria"]
    districts = list(settings["districts"])
    max_price = float(settings["profiles"]["大樓公寓華廈"]["max_price"])
    crawler = BrowserRakuyaPilotCrawler(
        districts=districts, max_price=max_price, max_pages=max_pages, headless=headless
    )
    listings = crawler.fetch()
    comparison = compare_with_current(listings, _load_current_listings(current_results_path))
    payload = {
        "generated_at": datetime.now(ZoneInfo("Asia/Taipei")).isoformat(),
        "mode": "pilot_only", "source": SOURCE_NAME,
        "filters": {
            "districts": districts, "max_price": max_price,
            "property_types": ["公寓", "大樓/華廈"], "resale_only": True,
        },
        "crawl": crawler.stats,
        "comparison": comparison,
        "listings": [item.to_dict() for item in listings],
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="樂屋網 1–3 頁低頻試爬與重複率報告")
    parser.add_argument("--pages", type=int, default=3, choices=(1, 2, 3))
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()
    result = run_pilot(max_pages=args.pages, headless=args.headless)
    crawl = result["crawl"]
    comparison = result["comparison"]
    print(f"樂屋頁面總數：{crawl['reported_total'] or '未取得'}")
    print(f"試爬唯一房源：{crawl['fetched']} 筆")
    print(f"保守判定與現有結果重複：{comparison['overlap_count']} 筆")
    print(f"尚未命中現有結果：{comparison['potential_new_count']} 筆")
    print(f"報告：{DEFAULT_REPORT}")


if __name__ == "__main__":
    main()
