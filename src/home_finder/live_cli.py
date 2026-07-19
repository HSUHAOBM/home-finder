from __future__ import annotations

import argparse
import json
from pathlib import Path

from .live_sources import JsonFileSource, Sale591PublicHtmlSource
from .models import Preferences
from .ranking import rank_listings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="抓取、篩選並排序適合你的房源")
    parser.add_argument("--config", default="config.live.json", help="來源與偏好設定 JSON")
    parser.add_argument("--input", help="離線房源 JSON；提供時不會連線")
    parser.add_argument("--limit", type=int, default=20, help="最多顯示幾筆")
    return parser


def build_source(config: dict, input_path: str | None):
    if input_path:
        return JsonFileSource(input_path)
    source = config.get("source", {})
    if source.get("type") != "591_sale_public_html":
        raise ValueError("source.type 目前支援 591_sale_public_html")
    return Sale591PublicHtmlSource(
        city=source["city"],
        region_id=int(source["region_id"]),
        pages=int(source.get("pages", 1)),
        delay_seconds=float(source.get("delay_seconds", 3)),
    )


def main() -> None:
    args = build_parser().parse_args()
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    preferences = Preferences.from_dict(config.get("preferences", {}))
    listings = build_source(config, args.input).fetch()
    all_ranked = rank_listings(listings, preferences)
    results = all_ranked[: args.limit]

    print(f"共讀取 {len(listings)} 筆，符合條件 {len(all_ranked)} 筆，本次顯示 {len(results)} 筆\n")
    for index, result in enumerate(results, start=1):
        item = result.listing
        print(f"{index}. [{result.score:.1f} 分] {item.title}")
        print(
            f"   {item.city}{item.district}｜{item.total_price_wan:.0f} 萬｜"
            f"{item.area_ping:g} 坪｜{item.rooms:g} 房｜{item.price_per_ping_wan:.1f} 萬/坪"
        )
        if result.reasons:
            print(f"   適合原因：{'；'.join(result.reasons)}")
        print(f"   {item.url}\n")

    if not all_ranked:
        print("目前取得的公開 HTML 房源沒有符合條件；這不代表網站上沒有其他合適物件。")


if __name__ == "__main__":
    main()
