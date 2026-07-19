import copy

import pytest

from home_finder import web_app_v3
from home_finder.user_models import HomeListing
from home_finder.user_ranking_v4 import evaluate_listing


def test_settings_reject_target_above_maximum():
    settings = copy.deepcopy(web_app_v3.DEFAULT_SETTINGS)
    settings["profiles"]["大樓公寓華廈"]["target_price"] = 1200
    settings["profiles"]["大樓公寓華廈"]["max_price"] = 1100

    with pytest.raises(ValueError, match="目標總價不能高於總價上限"):
        web_app_v3.validate_settings(settings)


def test_changed_area_threshold_re_evaluates_listing():
    listing = HomeListing(
        source="591中古屋",
        external_id="A",
        title="測試房源",
        url="https://example.com/A",
        city="高雄市",
        district="楠梓區",
        total_price_wan=1100,
        property_type="電梯大樓",
        main_area_ping=18,
        rooms=2,
        baths=2,
        age_years=5,
        parking_type="平面式",
        has_parking=True,
    )
    settings = copy.deepcopy(web_app_v3.DEFAULT_SETTINGS)
    assert evaluate_listing(listing, "大樓公寓華廈", settings).status == "qualified"

    settings["profiles"]["大樓公寓華廈"]["min_main_area"] = 20
    result = evaluate_listing(listing, "大樓公寓華廈", settings)
    assert result.status == "rejected"
    assert "低於最低 20" in result.hard_failures[0]


def test_v3_homepage_has_settings_and_three_goals():
    page = web_app_v3.app.test_client().get("/").get_data(as_text=True)
    assert "調整條件" in page
    assert "大樓・公寓・華廈" in page
    assert "透天・車墅" in page
    assert "預售屋" in page
