from __future__ import annotations

import math

from .user_models import Evaluation, HomeListing, ProfileName
from .user_ranking import find_duplicate_groups
from .user_ranking_v4 import evaluate_listing as _evaluate_listing


def evaluate_listing(listing: HomeListing, profile: ProfileName, settings: dict) -> Evaluation:
    result = _evaluate_listing(listing, profile, settings)
    config = settings["profiles"][profile]
    if profile == "大樓公寓華廈" and config.get("require_high_floor"):
        ratio = float(config.get("min_floor_ratio", 2 / 3))
        if listing.current_floor is None or not listing.total_floors:
            if "樓層資料不明" not in result.missing_required:
                result.missing_required.append("樓層資料不明")
        else:
            minimum_floor = math.ceil(listing.total_floors * ratio - 1e-9)
            if listing.current_floor < minimum_floor:
                result.hard_failures.append(
                    f"位於 {listing.current_floor}/{listing.total_floors} 樓，"
                    f"低於最低 {minimum_floor} 樓（全棟 2/3）"
                )
        if result.hard_failures:
            result.status = "rejected"
        elif result.missing_required:
            result.status = "needs_verification"
    return result


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
