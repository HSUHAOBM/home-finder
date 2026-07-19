from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from .crawler_591_browser_v3 import Browser591Crawler
from .crawler_591_presale import Browser591PresaleCrawler
from .user_models import HomeListing
from .user_ranking_v2 import evaluate_all


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="依三套個人條件搜尋高雄房源")
    parser.add_argument("--config", default="config.user.json")
    parser.add_argument("--input", help="離線 JSON；提供時不連線")
    parser.add_argument("--output", default="output/all-results.json")
    parser.add_argument("--include-rejected", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    if args.input:
        raw = json.loads(Path(args.input).read_text(encoding="utf-8"))
        listings = [HomeListing.from_dict(item) for item in raw]
    else:
        source = config["source"]
        districts = source["districts"]
        resale = Browser591Crawler(
            districts=districts,
            max_details=int(source.get("max_details", 20)),
            delay_seconds=float(source.get("delay_seconds", 2)),
            headless=bool(source.get("headless", True)),
        ).fetch()
        presale = Browser591PresaleCrawler(
            districts=districts,
            max_details=int(source.get("presale_max_details", 12)),
            delay_seconds=float(source.get("delay_seconds", 2)),
            headless=bool(source.get("headless", True)),
        ).fetch()
        listings = resale + presale

    results = evaluate_all(listings)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps([item.to_dict() for item in results], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    counts = Counter(item.status for item in results)
    print(
        f"房源 {len(listings)} 筆；合格 {counts['qualified']}、"
        f"待確認 {counts['needs_verification']}、淘汰 {counts['rejected']}"
    )
    print(f"完整報告：{output.resolve()}\n")
    for result in results:
        if result.status == "rejected" and not args.include_rejected:
            continue
        item = result.listing
        status = {"qualified": "合格", "needs_verification": "待確認", "rejected": "淘汰"}[result.status]
        price = f"{item.total_price_wan:g} 萬" if item.total_price_wan > 0 else "總價待確認"
        print(f"[{status}｜{result.profile}｜{result.score:.1f}] {item.title}")
        print(
            f"  {item.district}｜{price}｜主建 "
            f"{item.main_area_ping if item.main_area_ping is not None else '?'} 坪｜"
            f"{item.rooms if item.rooms is not None else '?'} 房｜車位 {item.parking_type or '?'}"
        )
        if result.strengths:
            print("  優點：" + "；".join(result.strengths))
        if result.missing_required:
            print("  待確認：" + "；".join(result.missing_required))
        if result.concerns:
            print("  注意：" + "；".join(result.concerns))
        if result.duplicate_ids:
            print("  疑似重複：" + ", ".join(result.duplicate_ids))
        print(f"  {item.url}\n")


if __name__ == "__main__":
    main()
