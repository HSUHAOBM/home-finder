from __future__ import annotations

import re
from collections import defaultdict

from .user_models import Evaluation, HomeListing, ProfileName


TARGET_DISTRICTS = {"楠梓區", "三民區", "橋頭區", "大社區"}
CONDO_TYPES = {"電梯大樓", "公寓", "華廈"}
HOUSE_TYPES = {"透天厝", "別墅"}


def _normalize_location(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"[\s,，、路街巷弄號之-]", "", value.lower())


def duplicate_key(listing: HomeListing) -> tuple | None:
    location = _normalize_location(listing.community) or _normalize_location(listing.address)
    if not location:
        return None
    area = listing.total_area_ping or listing.main_area_ping
    return (
        listing.district,
        location,
        round(area, 1) if area is not None else None,
        listing.rooms,
        listing.current_floor,
    )


def find_duplicate_groups(listings: list[HomeListing]) -> dict[str, list[str]]:
    buckets: dict[tuple, list[HomeListing]] = defaultdict(list)
    for listing in listings:
        key = duplicate_key(listing)
        if key is not None:
            buckets[key].append(listing)

    result: dict[str, list[str]] = {}
    for group in buckets.values():
        if len(group) < 2:
            continue
        ids = [item.external_id for item in group]
        for item in group:
            result[item.external_id] = [value for value in ids if value != item.external_id]
    return result


def _required_number(
    value: float | None,
    minimum: float,
    label: str,
    failures: list[str],
    missing: list[str],
) -> None:
    if value is None:
        missing.append(f"{label}資料不明")
    elif value < minimum:
        failures.append(f"{label} {value:g}，低於最低 {minimum:g}")


def _require_parking(
    listing: HomeListing,
    flat_only: bool,
    failures: list[str],
    missing: list[str],
) -> None:
    if listing.has_parking is False or listing.parking_type == "無":
        failures.append("詳情欄位顯示無汽車位")
        return
    if listing.has_parking is None and listing.parking_type is None:
        missing.append("汽車位資料不明")
        return
    if flat_only:
        if listing.parking_type is None:
            missing.append("車位存在，但無法確認是否為平面車位")
        elif "平面" not in listing.parking_type:
            failures.append(f"不是平面車位：{listing.parking_type}")


def _base_checks(listing: HomeListing) -> tuple[list[str], list[str]]:
    failures: list[str] = []
    missing: list[str] = []
    if listing.city != "高雄市":
        failures.append("不在高雄市")
    if listing.district not in TARGET_DISTRICTS:
        failures.append("不在楠梓、三民、橋頭或大社")
    if listing.total_price_wan > 1200:
        failures.append(f"總價 {listing.total_price_wan:g} 萬，超過 1200 萬")
    return failures, missing


def evaluate_listing(listing: HomeListing, profile: ProfileName) -> Evaluation:
    failures, missing = _base_checks(listing)
    strengths: list[str] = []
    concerns = list(listing.data_warnings)
    score = 50.0

    if profile == "大樓公寓華廈":
        if listing.deal_kind != "中古屋":
            failures.append("不是中古屋")
        if listing.property_type is None:
            missing.append("建物型態不明")
        elif listing.property_type not in CONDO_TYPES:
            failures.append(f"建物型態是 {listing.property_type}，不是大樓／公寓／華廈")
        _require_parking(listing, flat_only=True, failures=failures, missing=missing)
        _required_number(listing.main_area_ping, 15, "主建物坪數", failures, missing)
        _required_number(listing.rooms, 2, "房數", failures, missing)
    elif profile == "透天別墅":
        if listing.deal_kind != "中古屋":
            failures.append("不是中古屋")
        if listing.property_type is None:
            missing.append("建物型態不明，不能只憑標題認定透天／別墅")
        elif listing.property_type not in HOUSE_TYPES:
            failures.append(f"詳情型態是 {listing.property_type}，排除疑似混入的車墅廣告")
        _require_parking(listing, flat_only=False, failures=failures, missing=missing)
    else:
        if listing.deal_kind != "預售屋":
            failures.append("不是預售屋")
        _require_parking(listing, flat_only=True, failures=failures, missing=missing)
        _required_number(listing.main_area_ping, 15, "主建物坪數", failures, missing)
        _required_number(listing.rooms, 2, "房數", failures, missing)

    if listing.total_price_wan <= 1100:
        score += 15
        strengths.append("總價在 1100 萬目標內")
    else:
        score += max(0, 15 - (listing.total_price_wan - 1100) / 10)
        concerns.append("總價介於 1100 至 1200 萬")

    if listing.age_years is None:
        concerns.append("屋齡資料不明")
    elif listing.age_years <= 10:
        score += 10
        strengths.append("屋齡 10 年內")
    elif listing.age_years <= 30:
        score += 6
        strengths.append("屋齡 30 年內")
    else:
        concerns.append(f"屋齡 {listing.age_years:g} 年，超過偏好 30 年")

    if listing.baths is not None and listing.baths >= 2:
        score += 8
        strengths.append("有 2 衛浴以上")
    elif profile != "透天別墅":
        concerns.append("未達 2 衛浴偏好" if listing.baths is not None else "衛浴數不明")

    if profile == "大樓公寓華廈":
        if listing.current_floor is not None and listing.current_floor == listing.total_floors:
            score += 12
            strengths.append("位於頂樓，上方無住戶")
        elif listing.floor_ratio is not None and listing.floor_ratio >= 0.8:
            score += 9
            strengths.append("位於相對高樓層")
        elif listing.floor_ratio is not None and listing.floor_ratio >= 0.6:
            score += 4
            strengths.append("樓層在全棟中段以上")
        else:
            concerns.append("未確認符合高樓層偏好")

    if profile == "透天別墅" and listing.has_garden:
        score += 10
        strengths.append("描述提到花園")

    if failures:
        status = "rejected"
    elif missing:
        status = "needs_verification"
    else:
        status = "qualified"

    return Evaluation(
        listing=listing,
        profile=profile,
        status=status,
        score=round(min(score, 100), 1),
        hard_failures=failures,
        missing_required=missing,
        strengths=strengths,
        concerns=concerns,
    )


def evaluate_all(listings: list[HomeListing]) -> list[Evaluation]:
    duplicates = find_duplicate_groups(listings)
    results: list[Evaluation] = []
    profiles: tuple[ProfileName, ...] = ("大樓公寓華廈", "透天別墅", "預售屋")
    for listing in listings:
        for profile in profiles:
            result = evaluate_listing(listing, profile)
            result.duplicate_ids = duplicates.get(listing.external_id, [])
            results.append(result)
    order = {"qualified": 0, "needs_verification": 1, "rejected": 2}
    return sorted(results, key=lambda item: (order[item.status], -item.score, item.listing.total_price_wan))
