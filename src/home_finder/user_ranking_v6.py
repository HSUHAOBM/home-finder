from __future__ import annotations

import math

from .user_models import Evaluation, HomeListing, ProfileName
from .user_ranking import duplicate_ref, find_duplicate_groups
from .user_ranking_v4 import evaluate_listing as _evaluate_listing


def evaluate_listing(listing: HomeListing, profile: ProfileName, settings: dict) -> Evaluation:
    """Evaluate a listing while treating the 2/3 floor rule as a preference by default."""
    result = _evaluate_listing(listing, profile, settings)
    config = settings["profiles"][profile]

    if profile != "大樓公寓華廈" or not config.get("prefer_high_floor"):
        return result

    ratio = float(config.get("min_floor_ratio", 2 / 3))
    ratio_label = "2/3" if abs(ratio - 2 / 3) < 0.001 else f"{ratio:.0%}"
    if listing.current_floor is None or not listing.total_floors:
        if config.get("require_high_floor"):
            if "樓層資料不明" not in result.missing_required:
                result.missing_required.append("樓層資料不明")
        elif "樓層資料不明，需確認是否達高樓層偏好" not in result.concerns:
            result.concerns.append("樓層資料不明，需確認是否達高樓層偏好")
    else:
        minimum_floor = math.ceil(listing.total_floors * ratio - 1e-9)
        if listing.current_floor >= minimum_floor:
            result.score = round(min(100, result.score + 5), 1)
            result.strengths.append(
                f"位於 {listing.current_floor}/{listing.total_floors} 樓，達全棟 {ratio_label} 高度偏好"
            )
        elif config.get("require_high_floor"):
            result.hard_failures.append(
                f"位於 {listing.current_floor}/{listing.total_floors} 樓，"
                f"低於最低 {minimum_floor} 樓（全棟 {ratio_label}）"
            )
        else:
            if "未確認符合高樓層偏好" in result.concerns:
                result.concerns.remove("未確認符合高樓層偏好")
            result.concerns.append(
                f"位於 {listing.current_floor}/{listing.total_floors} 樓，"
                f"未達偏好樓層 {minimum_floor} 樓（全棟 {ratio_label}）"
            )

    if result.hard_failures:
        result.status = "rejected"
    elif result.missing_required:
        result.status = "needs_verification"
    else:
        result.status = "qualified"
    return result


def evaluate_all(listings: list[HomeListing], settings: dict) -> list[Evaluation]:
    duplicates = find_duplicate_groups(listings)
    profiles: tuple[ProfileName, ...] = ("大樓公寓華廈", "透天別墅", "預售屋")
    results: list[Evaluation] = []
    for listing in listings:
        for profile in profiles:
            result = evaluate_listing(listing, profile, settings)
            result.duplicate_ids = duplicates.get(duplicate_ref(listing), [])
            results.append(result)
    order = {"qualified": 0, "needs_verification": 1, "rejected": 2}
    return sorted(
        results,
        key=lambda item: (order[item.status], -item.score, item.listing.total_price_wan),
    )
