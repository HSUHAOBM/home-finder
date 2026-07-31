from __future__ import annotations

import copy
from pathlib import Path
from datetime import datetime, timedelta, timezone

import pytest

from home_finder.crawler_591_multi import UPDATE_TEXT
from home_finder.listing_history import annotate_history
from home_finder.user_models import HomeListing
from home_finder.user_ranking_v5 import evaluate_listing
from home_finder.web_app_v4 import DEFAULT_SETTINGS, validate_settings


def listing(**changes):
    values = dict(
        source="591中古屋",
        external_id="A",
        title="測試房源",
        url="https://example.com/A",
        city="高雄市",
        district="楠梓區",
        total_price_wan=1000,
        property_type="電梯大樓",
        main_area_ping=18,
        rooms=2,
        baths=2,
        age_years=5,
        current_floor=10,
        total_floors=15,
        parking_type="平面式",
        has_parking=True,
        search_profile="大樓公寓華廈",
        listing_updated_text="5分鐘前更新",
    )
    values.update(changes)
    return HomeListing(**values)


def test_floor_two_thirds_accepts_tenth_of_fifteen():
    result = evaluate_listing(listing(), "大樓公寓華廈", copy.deepcopy(DEFAULT_SETTINGS))
    assert result.status == "qualified"


def test_floor_below_two_thirds_is_rejected():
    result = evaluate_listing(
        listing(current_floor=9), "大樓公寓華廈", copy.deepcopy(DEFAULT_SETTINGS)
    )
    assert result.status == "rejected"
    assert "低於最低 10 樓" in result.hard_failures[-1]


def test_missing_floor_needs_verification():
    result = evaluate_listing(
        listing(current_floor=None, total_floors=None),
        "大樓公寓華廈",
        copy.deepcopy(DEFAULT_SETTINGS),
    )
    assert result.status == "needs_verification"
    assert "樓層資料不明" in result.missing_required


def test_history_marks_new_seen_and_updated(tmp_path):
    path = tmp_path / "history.json"
    first_time = datetime(2026, 7, 16, tzinfo=timezone.utc)
    first = annotate_history([listing()], path=path, now=first_time)[0]
    assert first.lifecycle_status == "new"

    seen = annotate_history([listing()], path=path, now=first_time + timedelta(hours=1))[0]
    assert seen.lifecycle_status == "seen"
    assert seen.first_seen_at == first.first_seen_at

    relative_text_only = annotate_history(
        [listing(listing_updated_text="1分鐘前更新")],
        path=path,

        now=first_time + timedelta(hours=2),
    )[0]
    assert relative_text_only.lifecycle_status == "seen"
    assert relative_text_only.change_details == []

    updated = annotate_history(
        [listing(total_price_wan=950, listing_updated_text="剛剛更新")],
        path=path,
        now=first_time + timedelta(hours=3),
    )[0]
    assert updated.lifecycle_status == "updated"
    assert updated.change_details == ["總價：1000 萬 → 950 萬"]



def test_update_label_ui_shows_actual_change_details():
    static_dir = Path(__file__).parents[1] / "src" / "home_finder" / "static"
    script = (static_dir / "dashboard_v4.js").read_text(encoding="utf-8")
    stylesheet = (static_dir / "dashboard_v4.css").read_text(encoding="utf-8")
    assert "這次實際變更" in script
    assert "舊版更新紀錄" in script
    assert "change_details" in script
    assert ".change-details" in stylesheet


def test_history_keeps_same_external_id_from_different_sources(tmp_path):
    path = tmp_path / "history.json"
    now = datetime(2026, 7, 28, tzinfo=timezone.utc)
    first, second = annotate_history(
        [listing(source="591中古屋"), listing(source="永慶房仲網")],
        path=path,
        now=now,
    )
    assert first.lifecycle_status == "new"
    assert second.lifecycle_status == "new"
    payload = path.read_text(encoding="utf-8")
    assert '"591中古屋:A"' in payload and '"永慶房仲網:A"' in payload


def test_update_text_parser():
    assert UPDATE_TEXT.search("12分鐘前更新 近一週10次曝光").group(0) == "12分鐘前更新"


def test_settings_require_at_least_three_pages():
    settings = copy.deepcopy(DEFAULT_SETTINGS)
    settings["search"]["pages"] = 2
    with pytest.raises(ValueError, match="每種中古屋頁數"):
        validate_settings(settings)
