from __future__ import annotations

import argparse
import json
from pathlib import Path

from .models import Preferences
from .ranking import rank_listings
from .sources import JsonFileSource


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="依個人條件篩選並排序房源")
    parser.add_argument("--config", default="config.json", help="偏好設定 JSON")
    parser.add_argument("--input", default="examples/sample_listings.json", help="房源資料 JSON")
    parser.add_argument("--limit", type=int, default=20, help="最多顯示幾筆")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    preferences = Preferences.from_dict(config)
    listings = JsonFileSource(args.input).fetch()
    results = rank_listings(listings, preferences)[: args.limit]

    print(f"共讀取 {len(listings)} 筆，找到 {len(results)} 筆符合條件的房源\n")
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


if __name__ == "__main__":
    main()
