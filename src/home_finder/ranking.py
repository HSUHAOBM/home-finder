from __future__ import annotations

from .models import Listing, Preferences, RankedListing


def rejection_reasons(listing: Listing, preferences: Preferences) -> list[str]:
    reasons: list[str] = []
    text = listing.searchable_text

    if preferences.cities and listing.city not in preferences.cities:
        reasons.append("不在指定縣市")
    if preferences.districts and listing.district not in preferences.districts:
        reasons.append("不在指定行政區")
    if (
        preferences.max_total_price_wan is not None
        and listing.total_price_wan > preferences.max_total_price_wan
    ):
        reasons.append("超出總價上限")
    if preferences.min_area_ping is not None and listing.area_ping < preferences.min_area_ping:
        reasons.append("坪數不足")
    if preferences.min_rooms is not None and listing.rooms < preferences.min_rooms:
        reasons.append("房數不足")
    if (
        preferences.max_age_years is not None
        and listing.age_years is not None
        and listing.age_years > preferences.max_age_years
    ):
        reasons.append("屋齡超出上限")
    missing = [word for word in preferences.required_keywords if word.lower() not in text]
    if missing:
        reasons.append(f"缺少必要條件：{', '.join(missing)}")
    excluded = [word for word in preferences.excluded_keywords if word.lower() in text]
    if excluded:
        reasons.append(f"含排除條件：{', '.join(excluded)}")
    return reasons


def score_listing(listing: Listing, preferences: Preferences) -> RankedListing | None:
    if rejection_reasons(listing, preferences):
        return None

    score = 50.0
    reasons: list[str] = []

    if preferences.max_total_price_wan:
        budget_ratio = listing.total_price_wan / preferences.max_total_price_wan
        budget_score = max(0.0, (1.0 - budget_ratio) * 25.0)
        score += budget_score
        reasons.append(f"總價低於預算上限 {preferences.max_total_price_wan - listing.total_price_wan:.0f} 萬")

    if preferences.min_area_ping:
        extra_area = listing.area_ping - preferences.min_area_ping
        score += min(10.0, max(0.0, extra_area) * 0.8)
        if extra_area > 0:
            reasons.append(f"比最低坪數多 {extra_area:.1f} 坪")

    if preferences.min_rooms and listing.rooms > preferences.min_rooms:
        score += min(5.0, (listing.rooms - preferences.min_rooms) * 2.5)
        reasons.append("房數高於最低需求")

    matched_keywords = [
        word for word in preferences.preferred_keywords if word.lower() in listing.searchable_text
    ]
    if matched_keywords:
        score += min(15.0, len(matched_keywords) * 5.0)
        reasons.append(f"符合偏好：{', '.join(matched_keywords)}")

    if listing.age_years is not None and preferences.max_age_years:
        age_headroom = preferences.max_age_years - listing.age_years
        score += min(5.0, max(0.0, age_headroom / preferences.max_age_years * 5.0))

    return RankedListing(listing=listing, score=round(min(100.0, score), 1), reasons=tuple(reasons))


def rank_listings(listings: list[Listing], preferences: Preferences) -> list[RankedListing]:
    ranked = [result for listing in listings if (result := score_listing(listing, preferences))]
    return sorted(ranked, key=lambda item: (-item.score, item.listing.total_price_wan))
