from home_finder.user_models import HomeListing
from home_finder.user_ranking_v3 import evaluate_listing


def test_presale_estimated_private_area_below_15_is_rejected() -> None:
    listing = HomeListing(
        source="test",
        external_id="small",
        title="小兩房",
        url="https://example.com/small",
        city="高雄市",
        district="楠梓區",
        total_price_wan=0,
        deal_kind="預售屋",
        rooms=2,
        age_years=0,
        data_warnings=["以 2 房銷售坪數與公設比粗估室內約 14.2 坪；含附屬建物"],
    )
    result = evaluate_listing(listing, "預售屋")
    assert result.status == "rejected"
    assert any("低於 15 坪門檻" in failure for failure in result.hard_failures)
