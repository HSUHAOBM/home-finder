from __future__ import annotations

import csv
import io
import re
import statistics
import urllib.request
import zipfile
import math
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable


OFFICIAL_QUERY_URL = "https://lvr.land.moi.gov.tw/"
DOWNLOAD_URL = (
    "https://plvr.land.moi.gov.tw/DownloadSeason?season={season}"
    "&type=zip&fileName=lvr_landcsv.zip"
)
KAOHSIUNG_CSV = "e_lvr_land_a.csv"
PING_PER_SQM = 1 / 3.305785


def _recent_seasons(current: date, months: int = 12) -> tuple[str, ...]:
    year = current.year - 1911
    quarter = (current.month - 1) // 3 + 1
    quarter -= 1
    if quarter == 0:
        year -= 1
        quarter = 4
    seasons = []
    for _ in range(max(4, math.ceil(months / 3))):
        seasons.append(f"{year}S{quarter}")
        quarter -= 1
        if quarter == 0:
            year -= 1
            quarter = 4
    return tuple(reversed(seasons))


def _download(url: str, target: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "home-finder/1.0"})
    part = target.with_suffix(".part")
    with urllib.request.urlopen(request, timeout=120) as response:
        part.write_bytes(response.read())
    with zipfile.ZipFile(part) as archive:
        if KAOHSIUNG_CSV not in archive.namelist():
            raise ValueError("官方季度檔缺少高雄市買賣資料")
    part.replace(target)


def _text(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "")).replace("台", "臺")


def _road(value: Any) -> str:
    text = _text(value)
    text = re.sub(r"^[\u4e00-\u9fff]{1,4}[市縣]", "", text)
    text = re.sub(r"^[\u4e00-\u9fff]{1,4}[區鄉鎮市]", "", text)
    match = re.search(r"([\u4e00-\u9fff]{1,12}(?:大道|路|街)(?:[一二三四五六七八九十百\d]+段)?)", text)
    return match.group(1) if match else ""


def _house_number(value: Any) -> int | None:
    match = re.search(r"(\d+)號", _text(value))
    return int(match.group(1)) if match else None


def _number_matches(listing_address: Any, transaction_address: Any) -> bool:
    number = _house_number(listing_address)
    if number is None:
        return False
    text = _text(transaction_address)
    numbers = [int(value) for value in re.findall(r"\d+", text)]
    if not numbers:
        return False
    if "~" in text or "～" in text or "至" in text:
        return min(numbers) <= number <= max(numbers)
    return number in numbers


def _roc_date(value: Any) -> date | None:
    digits = re.sub(r"\D", "", str(value or ""))
    if len(digits) < 7:
        return None
    digits = digits[-7:]
    try:
        return date(int(digits[:3]) + 1911, int(digits[3:5]), int(digits[5:7]))
    except ValueError:
        return None


def _number(value: Any) -> float | None:
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


_CHINESE_DIGITS = {"零": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
                   "六": 6, "七": 7, "八": 8, "九": 9}


def _floor_number(value: Any) -> int | None:
    text = str(value or "")
    match = re.search(r"\d+", text)
    if match:
        return int(match.group())
    text = text.replace("層", "").replace("樓", "")
    match = re.search(r"([一二三四五六七八九]?十[一二三四五六七八九]?|[一二三四五六七八九])", text)
    if not match:
        return None
    token = match.group(1)
    if "十" in token:
        left, right = token.split("十", 1)
        return (_CHINESE_DIGITS.get(left, 1) * 10) + _CHINESE_DIGITS.get(right, 0)
    return _CHINESE_DIGITS.get(token)


def _completion_year(value: Any) -> int | None:
    digits = re.sub(r"\D", "", str(value or ""))
    if len(digits) < 3:
        return None
    year = int(digits[:3]) + 1911
    return year if 1900 <= year <= date.today().year else None


def _record(row: dict[str, Any]) -> dict[str, Any] | None:
    traded = _roc_date(row.get("交易年月日"))
    total = _number(row.get("總價元"))
    area_sqm = _number(row.get("建物移轉總面積平方公尺"))
    unit_sqm = _number(row.get("單價元平方公尺"))
    if not traded or not total or total <= 0 or not area_sqm or area_sqm <= 0:
        return None
    unit_ping = (unit_sqm * 3.305785 / 10_000) if unit_sqm else (total / area_sqm * 3.305785 / 10_000)
    return {
        "date": traded.isoformat(),
        "address": str(row.get("土地位置建物門牌") or "").strip(),
        "total_price_wan": round(total / 10_000, 1),
        "unit_price_wan_ping": round(unit_ping, 2),
        "area_ping": round(area_sqm * PING_PER_SQM, 2),
        "floor": str(row.get("移轉層次") or "").strip(),
        "floor_number": _floor_number(row.get("移轉層次")),
        "total_floors": _floor_number(row.get("總樓層數")),
        "building_type": str(row.get("建物型態") or "").strip(),
        "completion_year": _completion_year(row.get("建築完成年月")),
        "parking": str(row.get("車位類別") or "").strip() or "無",
        "rooms": _number(row.get("建物現況格局-房")),
        "note": str(row.get("備註") or "").strip(),
    }


def _closeness(left: float, right: float, tolerance: float) -> float:
    return max(0.0, 1.0 - abs(left - right) / tolerance)


def _rank_record(item: dict[str, Any], listing: dict[str, Any], current: date) -> dict[str, Any]:
    score = 0.0
    weight = 0.0
    reasons: list[str] = []
    differences: list[str] = []

    community = _text(listing.get("community"))
    address_match = _number_matches(listing.get("address"), item["address"])
    community_match = bool(community and community in _text(item["address"] + item["note"]))
    weight += 35
    if community_match:
        score += 35
        reasons.append("社區名稱吻合")
    elif address_match:
        score += 33
        reasons.append("門牌範圍吻合")
    else:
        reasons.append("同路段")

    listing_area = _number(listing.get("total_area"))
    if listing_area:
        weight += 20
        closeness = _closeness(listing_area, item["area_ping"], max(listing_area * 0.4, 8))
        score += 20 * closeness
        delta = round(item["area_ping"] - listing_area, 1)
        (reasons if abs(delta) <= listing_area * 0.1 else differences).append(
            f"坪數{'相近' if abs(delta) <= listing_area * 0.1 else f'差 {delta:+g} 坪'}"
        )

    listing_rooms = _number(listing.get("rooms"))
    if listing_rooms and item.get("rooms"):
        weight += 8
        if listing_rooms == item["rooms"]:
            score += 8
            reasons.append("房數相同")
        else:
            differences.append(f"房數 {int(item['rooms'])} 房")

    listing_floor = _number(listing.get("floor"))
    if listing_floor and item.get("floor_number"):
        weight += 10
        score += 10 * _closeness(listing_floor, item["floor_number"], 8)
        delta = item["floor_number"] - listing_floor
        (reasons if abs(delta) <= 2 else differences).append(
            "樓層相近" if abs(delta) <= 2 else f"成交樓層差 {delta:+g} 層"
        )

    listing_total = _number(listing.get("total_floors"))
    if listing_total and item.get("total_floors"):
        weight += 10
        score += 10 * _closeness(listing_total, item["total_floors"], 6)
        if listing_total == item["total_floors"]:
            reasons.append("總樓層相同")
        else:
            differences.append(f"總樓層 {item['total_floors']} 層")

    listing_age = _number(listing.get("age"))
    transaction_age = current.year - item["completion_year"] if item.get("completion_year") else None
    item["age_at_query"] = transaction_age
    if listing_age is not None and transaction_age is not None:
        weight += 10
        age_delta = transaction_age - listing_age
        score += 10 * _closeness(listing_age, transaction_age, 10)
        (reasons if abs(age_delta) <= 1 else differences).append(
            "屋齡相近" if abs(age_delta) <= 1 else f"屋齡差 {age_delta:+g} 年"
        )

    listing_parking = _text(listing.get("parking"))
    if listing_parking:
        weight += 4
        if ("平面" in listing_parking) == ("平面" in item["parking"]):
            score += 4
            reasons.append("車位類型相近")
        else:
            differences.append(f"車位為 {item['parking']}")

    listing_type = _text(listing.get("property_type"))
    transaction_type = _text(item.get("building_type"))
    if listing_type and transaction_type:
        weight += 3
        same_type = any(name in listing_type and name in transaction_type for name in ("大樓", "華廈", "公寓", "透天"))
        if same_type:
            score += 3
            reasons.append("建物型態相近")
        else:
            differences.append(f"型態為 {item['building_type']}")

    normalized = round(score / weight * 100) if weight else 0
    same_building_signals = int(community_match or address_match)
    same_building_signals += int(bool(listing_total and item.get("total_floors") == listing_total))
    same_building_signals += int(bool(listing_age is not None and transaction_age is not None and abs(transaction_age - listing_age) <= 1))
    if same_building_signals >= 3 and normalized >= 85:
        label = "極可能同一棟"
    elif same_building_signals >= 2 and normalized >= 75:
        label = "可能同一棟"
    elif normalized >= 80:
        label = "高度相近"
    elif normalized >= 65:
        label = "條件相近"
    else:
        label = "同路段參考"
    item.update({
        "similarity_score": normalized,
        "similarity_label": label,
        "similarity_reasons": reasons,
        "differences": differences,
    })
    return item


def _load_season(path: Path) -> list[dict[str, Any]]:
    with zipfile.ZipFile(path) as archive:
        raw = archive.read(KAOHSIUNG_CSV).decode("utf-8-sig")
    rows = csv.DictReader(io.StringIO(raw))
    result = []
    for index, row in enumerate(rows):
        if index == 0 and row.get("鄉鎮市區") == "The villages and towns urban district":
            continue
        item = _record(row)
        if item:
            item["district"] = str(row.get("鄉鎮市區") or "").strip()
            result.append(item)
    return result


def _summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    prices = [item["unit_price_wan_ping"] for item in records]
    return {
        "count": len(records),
        "median_unit_price": round(statistics.median(prices), 2),
        "min_unit_price": round(min(prices), 2),
        "max_unit_price": round(max(prices), 2),
        "latest_date": max(item["date"] for item in records),
    }


def query_real_price(
    listing: dict[str, Any], *, cache_dir: Path, months: int = 12,
    today: date | None = None, downloader: Callable[[str, Path], None] = _download,
) -> dict[str, Any]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    current = today or date.today()
    seasons = _recent_seasons(current, months)
    all_records: list[dict[str, Any]] = []
    for season in seasons:
        path = cache_dir / f"official-{season}.zip"
        if not path.exists():
            downloader(DOWNLOAD_URL.format(season=season), path)
        all_records.extend(_load_season(path))

    since = current - timedelta(days=round(months * 365.25 / 12))
    district = _text(listing.get("district"))
    listing_address = listing.get("address")
    road = _road(listing_address)
    community = _text(listing.get("community"))
    road_candidates = [
        item for item in all_records
        if _text(item["district"]) == district and date.fromisoformat(item["date"]) >= since
        and (not road or _road(item["address"]) == road)
    ]
    listing_area = _number(listing.get("total_area"))
    listing_rooms = _number(listing.get("rooms"))
    candidates = road_candidates
    exact = [
        item for item in candidates
        if (community and community in _text(item["address"] + item["note"]))
        or _number_matches(listing_address, item["address"])
    ]
    selected = exact or candidates
    match_level = "address" if exact else ("road" if candidates else "none")
    selected = [_rank_record(item, listing, current) for item in selected]
    selected.sort(key=lambda item: (item["similarity_score"], item["date"]), reverse=True)
    listing_price = _number(listing.get("price"))
    listing_unit_price = round(listing_price / listing_area, 2) if listing_price and listing_area else None
    return {
        "community": listing.get("community"),
        "district": listing.get("district"),
        "address": listing.get("address"),
        "road": road,
        "comparison_scope": (
            "依門牌、坪數、房數、樓層、總樓層、屋齡與車位綜合排序"
            if selected else "同路段"
        ),
        "months": months,
        "since": since.isoformat(),
        "match_level": match_level,
        "match_label": {"address": "門牌範圍吻合", "road": "同路段參考", "none": "查無相近成交"}[match_level],
        "summary": _summary(selected) if selected else None,
        "listing_unit_price": listing_unit_price,
        "transactions": selected[:30],
        "closest_matches": selected[:5],
        "source": "內政部不動產交易實價查詢服務網",
        "source_url": OFFICIAL_QUERY_URL,
        "seasons": list(seasons),
        "cached_at": datetime.now(timezone.utc).isoformat(),
        "notice": "官方開放資料未提供穩定社區名稱；門牌已去識別化，結果僅供比價參考。",
    }
