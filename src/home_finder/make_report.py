from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .result_store import read_result_records


def _value(value, suffix="") -> str:
    return f"{value:g}{suffix}" if isinstance(value, (int, float)) else "待確認"


def _listing_block(item: dict) -> list[str]:
    listing = item["listing"]
    price = _value(listing.get("total_price_wan"), " 萬") if listing.get("total_price_wan", 0) > 0 else "待確認"
    floor = (
        f"{listing['current_floor']}/{listing['total_floors']} 樓"
        if listing.get("current_floor") is not None and listing.get("total_floors")
        else "待確認"
    )
    lines = [
        f"### {listing['title']}",
        "",
        f"- 評分：{item['score']:.1f}｜區域：{listing['district']}｜總價：{price}",
        f"- 主建物：{_value(listing.get('main_area_ping'), ' 坪')}｜房數：{_value(listing.get('rooms'), ' 房')}｜衛浴：{_value(listing.get('baths'), ' 衛')}",
        f"- 車位：{listing.get('parking_type') or '待確認'}｜樓層：{floor}｜屋齡：{_value(listing.get('age_years'), ' 年')}",
    ]
    if item.get("strengths"):
        lines.append(f"- 優點：{'；'.join(item['strengths'])}")
    if item.get("missing_required"):
        lines.append(f"- 必問：{'；'.join(item['missing_required'])}")
    if item.get("concerns"):
        lines.append(f"- 注意：{'；'.join(item['concerns'])}")
    if item.get("duplicate_ids"):
        lines.append(f"- 疑似重複刊登：{', '.join(item['duplicate_ids'])}")
    lines.extend([f"- [開啟房源]({listing['url']})", ""])
    return lines


def render_report(results: list[dict]) -> str:
    unique_listings = {item["listing"]["external_id"] for item in results}
    status_counts = Counter(item["status"] for item in results)
    now = datetime.now(ZoneInfo("Asia/Taipei")).strftime("%Y-%m-%d %H:%M")
    lines = [
        "# 高雄購屋搜尋結果",
        "",
        f"更新時間：{now}（台北時間）",
        "",
        f"本次讀取 {len(unique_listings)} 筆房源，三方案評估結果為：合格 {status_counts['qualified']}、待確認 {status_counts['needs_verification']}、淘汰 {status_counts['rejected']}。",
        "",
        "> 主建物、車位型態與總價以詳情結構化欄位為準；預售屋的室內坪數估算不等於主建物謄本。",
        "",
    ]
    sections = [
        ("直接符合硬條件", "qualified"),
        ("值得詢問，但必要資料尚未確認", "needs_verification"),
    ]
    for heading, status in sections:
        lines.extend([f"## {heading}", ""])
        items = [item for item in results if item["status"] == status]
        if not items:
            lines.extend(["目前沒有。", ""])
        for item in items:
            lines.extend(_listing_block(item))

    failures = Counter(
        failure
        for item in results
        if item["status"] == "rejected"
        for failure in item.get("hard_failures", [])
    )
    lines.extend(["## 主要淘汰原因", ""])
    for failure, count in failures.most_common(10):
        lines.append(f"- {failure}：{count} 次方案評估")
    lines.extend(
        [
            "",
            "## 看屋前確認清單",
            "",
            "- 車位權狀與位置是否確實為坡道平面，不只看廣告標題。",
            "- 主建物是否至少 15 坪；不要用含公設與車位的權狀總坪數代替。",
            "- 總價是否包含車位，以及管理費是否另計車位坪數。",
            "- 同社區、相同坪數與樓層的多筆廣告是否其實是同一戶。",
            "- 頂樓或高樓層是否有漏水、設備層、機房與日曬問題。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="將搜尋 JSON 轉成 Markdown 摘要")
    parser.add_argument("--input", default="output/current-results.json")
    parser.add_argument("--output", default="output/current-summary.md")
    args = parser.parse_args()
    results = read_result_records(Path(args.input))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_report(results), encoding="utf-8")
    print(output.resolve())


if __name__ == "__main__":
    main()
