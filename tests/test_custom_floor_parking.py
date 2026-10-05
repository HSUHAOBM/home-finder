import copy
import json

import pytest

from home_finder.user_models import HomeListing
from home_finder.user_ranking_v6 import evaluate_listing
from home_finder.web_app_v4 import DEFAULT_SETTINGS, validate_settings
from home_finder import web_app_v4


def candidate(**changes):
    values = dict(source="test", external_id="custom", title="test", url="https://example.com",
                  city="高雄市", district="楠梓區", total_price_wan=1000,
                  property_type="電梯大樓", main_area_ping=18, rooms=2, baths=2,
                  age_years=5, current_floor=10, total_floors=15,
                  has_parking=True, parking_type="平面式")
    return HomeListing(**(values | changes))


def settings(**changes):
    result = copy.deepcopy(DEFAULT_SETTINGS)
    result["profiles"]["大樓公寓華廈"].update(changes)
    return validate_settings(result)


def test_required_floor_does_not_depend_on_preference_switch():
    result = evaluate_listing(candidate(current_floor=1), "大樓公寓華廈",
                              settings(require_high_floor=True, prefer_high_floor=False))
    assert result.status == "rejected"
    assert any("最低 10 樓" in failure for failure in result.hard_failures)


@pytest.mark.parametrize("floor,total,expected", [(9,15,"rejected"), (10,30,"qualified"),
                                                  (10,None,"qualified"), (None,15,"needs_verification")])
def test_absolute_floor_boundary_and_missing_total(floor, total, expected):
    result = evaluate_listing(candidate(current_floor=floor, total_floors=total), "大樓公寓華廈",
                              settings(floor_mode="absolute", min_floor=10))
    assert result.status == expected
    if expected == "qualified":
        assert "未確認符合高樓層偏好" not in result.concerns


@pytest.mark.parametrize("mode,parking,exists,expected", [
    ("any","機械式",True,"qualified"), ("any","無",False,"rejected"),
    ("flat","機械式",True,"rejected"), ("flat","平面式",True,"qualified"),
    ("none","無",False,"qualified"), ("any",None,None,"needs_verification"),
])
def test_parking_choices(mode, parking, exists, expected):
    config = settings(parking_requirement=mode)
    assert config["profiles"]["大樓公寓華廈"]["parking_requirement"] == mode
    result = evaluate_listing(candidate(parking_type=parking, has_parking=exists), "大樓公寓華廈", config)
    assert result.status == expected


@pytest.mark.parametrize("changes", [{"min_floor":0}, {"floor_mode":"invalid"}, {"parking_requirement":"invalid"}])
def test_invalid_custom_settings_are_rejected(changes):
    with pytest.raises(ValueError):
        settings(**changes)


def test_saved_choices_survive_reload(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"source": {}}), encoding="utf-8")
    monkeypatch.setattr(web_app_v4.base, "CONFIG_PATH", config_path)
    requested = settings(floor_mode="absolute", min_floor=12, parking_requirement="any")
    web_app_v4.save_settings(requested)
    loaded = web_app_v4.load_settings()["profiles"]["大樓公寓華廈"]
    assert loaded["floor_mode"] == "absolute"
    assert loaded["min_floor"] == 12
    assert loaded["parking_requirement"] == "any"
    assert evaluate_listing(candidate(current_floor=11), "大樓公寓華廈", web_app_v4.load_settings()).status == "rejected"
