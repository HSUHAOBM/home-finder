from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from .crawler_591_browser import Browser591Crawler
from .user_models import HomeListing
from .user_ranking import evaluate_all


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="高雄三方案購屋搜尋器")
    result.add_argument("--config", default="config.user.json")
    result.add_argument("--input", help="使用離線 JSON，不開啟瀏覽器")
    result.add_argument("--output", default="output/results.json")
    result.add_argument("--show-rejected", action="store_true")
    return result


def main() -> None:
    args = parser().parse_args()
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    if args.input:
        raw = json.loads(Path(args.input).read_text(encoding="utf-8"))
        listings = [HomeListing.from_dict(item) for item in raw]
    else:
        source = config["source"]
        listings = Browser591Crawler(
            districts=source["districts"],
            max_details=int(source.get("max_details", 20)),
            delay_seconds=float(source.get("delay_seconds", 2)),
            headless=bool(source.get("headless", True)),
        ).fetch()

    results = evaluate_all(listings)
    visible = [item for item in results if args.show_rejected or item.status != "rejected"]
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps([item.to_dict() for item in results], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    counts = Counter(item.status for item in results)
    print(
        f"讀取 {len(listings)} 筆；方案評估：合格 {counts['qualified']}、"
        f"待人工確認 {counts['needs_verification']}、淘汰 {counts['rejected']}"
    )
    print(f"完整結果：{output}\n")
    for item in visible:
        listing = item.listing
        label = {"qualified": "合格", "needs_verification": "待確認", "rejected": "淘汰"}[item.status]
        print(f"[{label}｜{item.profile}｜{item.score:.1f}] {listing.title}")
        print(
            f"  {listing.district}｜{listing.total_price_wan:g} 萬｜"
            f"主建 {listing.main_area_ping if listing.main_area_ping is not None else '?'} 坪｜"
            f"{listing.rooms if listing.rooms is not None else '?'} 房｜"
            f"車位 {listing.parking_type or '?'}"
        )
        if item.strengths:
            print("  優點：" + "；".join(item.strengths))
        if item.missing_required:
            print("  待確認：" + "；".join(item.missing_required))
        if item.concerns:
            print("  注意：" + "；".join(item.concerns))
        if item.duplicate_ids:
            print("  疑似重複刊登：" + ", ".join(item.duplicate_ids))
        print(f"  {listing.url}\n")


if __name__ == "__main__":
    main()
