from __future__ import annotations

import json
from pathlib import Path

from home_finder.deleted_listings import (
    load_deleted_listings,
    reconcile_relisted,
    record_deleted_listings,
)
from home_finder.user_models import HomeListing


def listing(external_id: str = "A") -> HomeListing:
    return HomeListing(
        source="591中古屋",
        external_id=external_id,
        title="重新上架測試",
        url=f"https://example.test/{external_id}",
        city="高雄市",
        district="仁武區",
        total_price_wan=1080,
        search_profile="透天別墅",
    )


def test_deleted_listing_keeps_tombstone_and_reappears_as_relisted(tmp_path: Path):
    path = tmp_path / "deleted.json"
    record_deleted_listings(
        path,
        [{
            "source": "591中古屋", "id": "A", "title": "舊標題",
            "url": "https://example.test/A", "profile": "透天別墅",
            "status": "acceptable", "price": 998,
        }],
        reason="manual_card_delete",
        deleted_at="2026-09-09T01:00:00+08:00",
    )

    active = reconcile_relisted(
        [listing()], path, relisted_at="2026-09-10T01:00:00+08:00"
    )[0]
    saved = load_deleted_listings(path)["items"]["591中古屋:A"]

    assert active.lifecycle_status == "relisted"
    assert "重新上架" in active.data_warnings[0]
    assert saved["state"] == "relisted"
    assert [event["action"] for event in saved["events"]] == ["deleted", "relisted"]


def test_deleted_listing_file_recovers_from_invalid_json(tmp_path: Path):
    path = tmp_path / "deleted.json"
    path.write_text("{broken", encoding="utf-8")

    assert load_deleted_listings(path) == {"version": 1, "items": {}}


def test_result_ui_separates_removed_and_supports_scoped_clear():
    root = Path(__file__).parents[1] / "src" / "home_finder" / "static"
    v7 = (root / "dashboard_v7.js").read_text(encoding="utf-8")
    v16 = (root / "dashboard_v16.js").read_text(encoding="utf-8")

    assert "刊登中／尚未確認" in v7
    assert "以下為已下架房源" in v7
    assert "一鍵清除此頁已下架" in v7
    assert "差強人意共 ${categoryItems.length} 筆" in v7
    assert "clear-current-category" in v7
    assert "listing-delete" in v16
    assert 'aria-label="刪除這張房源卡"' in v16
    assert 'actions.className = "card-actions"' in v16
    assert 'state.activeStatus === "favorites"' in v16
    assert 'supplemental.className = "listing-supplemental"' in v16
    assert 'if (!checked) return ""' in v16
    assert 'category: state.activeStatus' in v16
    assert "removed_only: Boolean(clearRemoved)" in v16
    assert "clear_category: Boolean(clearCategory)" in v16
    assert "完全符合、可接受、待確認、已排除與收藏都不會受影響" in v16
