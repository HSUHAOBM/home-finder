from __future__ import annotations

from .user_models import Evaluation, HomeListing, ProfileName
from .user_ranking import evaluate_listing as _evaluate_listing
from .user_ranking import find_duplicate_groups
from .user_ranking import duplicate_ref


def evaluate_listing(listing: HomeListing, profile: ProfileName) -> Evaluation:
    result = _evaluate_listing(listing, profile)
    if listing.total_price_wan <= 0:
        result.strengths = [value for value in result.strengths if "1100 萬" not in value]
        result.score = max(0, result.score - 15)
        if "總價資料不明" not in result.missing_required:
            result.missing_required.append("總價資料不明")
        if not result.hard_failures:
            result.status = "needs_verification"
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
