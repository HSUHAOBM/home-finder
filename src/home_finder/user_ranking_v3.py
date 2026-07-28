from __future__ import annotations

import re

from .user_models import Evaluation, HomeListing, ProfileName
from .user_ranking import find_duplicate_groups
from .user_ranking import duplicate_ref
from .user_ranking_v2 import evaluate_listing as _evaluate_listing


def evaluate_listing(listing: HomeListing, profile: ProfileName) -> Evaluation:
    result = _evaluate_listing(listing, profile)
    if profile == "預售屋":
        estimates = []
        for warning in listing.data_warnings:
            match = re.search(r"粗估室內約\s*([\d.]+)\s*坪", warning)
            if match:
                estimates.append(float(match.group(1)))
        if estimates and min(estimates) < 15:
            result.hard_failures.append(
                f"依銷售坪數與公設比估算，連附屬建物約 {min(estimates):g} 坪，低於 15 坪門檻"
            )
            result.status = "rejected"
    return result


def evaluate_all(listings: list[HomeListing]) -> list[Evaluation]:
    duplicates = find_duplicate_groups(listings)
    profiles: tuple[ProfileName, ...] = ("大樓公寓華廈", "透天別墅", "預售屋")
    results: list[Evaluation] = []
    for listing in listings:
        for profile in profiles:
            result = evaluate_listing(listing, profile)
            result.duplicate_ids = duplicates.get(duplicate_ref(listing), [])
            results.append(result)
    order = {"qualified": 0, "needs_verification": 1, "rejected": 2}
    return sorted(results, key=lambda item: (order[item.status], -item.score, item.listing.total_price_wan))
