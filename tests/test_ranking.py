from home_finder.models import Listing, Preferences
from home_finder.ranking import rank_listings, rejection_reasons


def listing(**changes) -> Listing:
    values = {
        "id": "1",
        "title": "近捷運電梯兩房",
        "url": "https://example.com/1",
        "city": "新北市",
        "district": "板橋區",
        "total_price_wan": 1500,
        "area_ping": 28,
        "rooms": 2,
        "age_years": 10,
        "tags": ("近捷運", "電梯"),
    }
    values.update(changes)
    return Listing(**values)


def test_hard_constraints_reject_over_budget() -> None:
    preferences = Preferences(max_total_price_wan=1400)
    assert rejection_reasons(listing(), preferences) == ["超出總價上限"]


def test_excluded_keyword_is_rejected() -> None:
    preferences = Preferences(excluded_keywords=("頂樓加蓋",))
    assert rejection_reasons(listing(title="低總價頂樓加蓋"), preferences) == [
        "含排除條件：頂樓加蓋"
    ]


def test_matching_preference_ranks_first() -> None:
    preferences = Preferences(
        max_total_price_wan=1800,
        min_area_ping=25,
        preferred_keywords=("車位",),
    )
    with_parking = listing(id="parking", title="兩房含車位", tags=("車位",))
    without_parking = listing(id="plain", title="一般兩房", tags=())
    ranked = rank_listings([without_parking, with_parking], preferences)
    assert [item.listing.id for item in ranked] == ["parking", "plain"]
