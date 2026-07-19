from __future__ import annotations

import re

from .user_models import Evaluation, HomeListing, ProfileName
from .user_ranking import CONDO_TYPES, HOUSE_TYPES, find_duplicate_groups


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


def evaluate_listing(
    listing: HomeListing,
    profile: ProfileName,
    settings: dict,
) -> Evaluation:
    config = settings["profiles"][profile]
    failures: list[str] = []
    missing: list[str] = []
    strengths: list[str] = []
    concerns = list(listing.data_warnings)
    score = 50.0

    if listing.city != "高雄市":
        failures.append("不在高雄市")
    if listing.district not in settings["districts"]:
        failures.append("不在目前勾選的行政區")

    max_price = float(config["max_price"])
    target_price = float(config["target_price"])
    if listing.total_price_wan <= 0:
        missing.append("總價資料不明")
    elif listing.total_price_wan > max_price:
        failures.append(f"總價 {listing.total_price_wan:g} 萬，超過 {max_price:g} 萬")
    elif listing.total_price_wan <= target_price:
        score += 15
        strengths.append(f"總價在 {target_price:g} 萬目標內")
    else:
        spread = max(max_price - target_price, 1)
        score += max(0, 15 * (max_price - listing.total_price_wan) / spread)
        concerns.append(f"總價高於 {target_price:g} 萬目標，仍在上限內")

    if profile == "大樓公寓華廈":
        if listing.deal_kind != "中古屋":
            failures.append("不是中古屋")
        if listing.property_type is None:
            missing.append("建物型態不明")
        elif listing.property_type not in CONDO_TYPES:
            failures.append(f"建物型態是 {listing.property_type}，不是大樓／公寓／華廈")
        if config["require_flat_parking"]:
            _require_parking(listing, True, failures, missing)
        _required_number(listing.main_area_ping, config["min_main_area"], "主建物坪數", failures, missing)
        _required_number(listing.rooms, config["min_rooms"], "房數", failures, missing)
    elif profile == "透天別墅":
        if listing.deal_kind != "中古屋":
            failures.append("不是中古屋")
        if listing.property_type is None:
            missing.append("建物型態不明，不能只憑標題認定透天／別墅")
        elif listing.property_type not in HOUSE_TYPES:
            failures.append(f"詳情型態是 {listing.property_type}，排除疑似混入的車墅廣告")
        if config["require_parking"]:
            _require_parking(listing, False, failures, missing)
    else:
        if listing.deal_kind != "預售屋":
            failures.append("不是預售屋")
        if config["require_flat_parking"]:
            _require_parking(listing, True, failures, missing)
        _required_number(listing.main_area_ping, config["min_main_area"], "主建物坪數", failures, missing)
        _required_number(listing.rooms, config["min_rooms"], "房數", failures, missing)
        estimates = []
        for warning in listing.data_warnings:
            match = re.search(r"粗估室內約\s*([\d.]+)\s*坪", warning)
            if match:
                estimates.append(float(match.group(1)))
        if estimates and min(estimates) < float(config["min_main_area"]):
            failures.append(
                f"依銷售坪數與公設比估算，連附屬建物約 {min(estimates):g} 坪，"
                f"低於 {float(config['min_main_area']):g} 坪門檻"
            )

    preferred_age = config.get("preferred_max_age")
    if preferred_age is not None:
        if listing.age_years is None:
            concerns.append("屋齡資料不明")
        elif listing.age_years <= 10:
            score += 10
            strengths.append("屋齡 10 年內")
        elif listing.age_years <= preferred_age:
            score += 6
            strengths.append(f"屋齡 {preferred_age:g} 年內")
        else:
            concerns.append(f"屋齡 {listing.age_years:g} 年，超過偏好 {preferred_age:g} 年")

    preferred_baths = config.get("preferred_min_baths")
    if preferred_baths is not None:
        if listing.baths is None:
            concerns.append("衛浴數不明")
        elif listing.baths >= preferred_baths:
            score += 8
            strengths.append(f"有 {preferred_baths:g} 衛浴以上")
        else:
            concerns.append(f"未達 {preferred_baths:g} 衛浴偏好")

    if profile == "大樓公寓華廈" and config.get("prefer_high_floor"):
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

    if profile == "透天別墅" and config.get("prefer_garden") and listing.has_garden:
        score += 10
        strengths.append("描述提到花園或庭院")

    status = "rejected" if failures else "needs_verification" if missing else "qualified"
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


def evaluate_all(listings: list[HomeListing], settings: dict) -> list[Evaluation]:
    duplicates = find_duplicate_groups(listings)
    profiles: tuple[ProfileName, ...] = ("大樓公寓華廈", "透天別墅", "預售屋")
    results: list[Evaluation] = []
    for listing in listings:
        for profile in profiles:
            result = evaluate_listing(listing, profile, settings)
            result.duplicate_ids = duplicates.get(listing.external_id, [])
            results.append(result)
    order = {"qualified": 0, "needs_verification": 1, "rejected": 2}
    return sorted(results, key=lambda item: (order[item.status], -item.score, item.listing.total_price_wan))
