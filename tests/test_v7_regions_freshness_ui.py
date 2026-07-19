from __future__ import annotations

import json
import os
import time
from pathlib import Path

from home_finder import web_app_v7
from home_finder.result_store import RANKING_VERSION, RESULT_SCHEMA_VERSION
from home_finder.user_models import HomeListing
from home_finder.user_ranking_v6 import evaluate_all


def listing(external_id: str = "A", **changes) -> HomeListing:
    values = dict(
        source="591中古屋",
        external_id=external_id,
        title="測試房源",
        url=f"https://example.com/{external_id}",
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
    )
    values.update(changes)
    return HomeListing(**values)


def test_all_kaohsiung_districts_have_presale_ids():
    assert len(web_app_v7.ALL_DISTRICTS) == 38
    assert set(web_app_v7.ALL_DISTRICTS) == set(web_app_v7.SECTION_IDS)
    assert web_app_v7.SECTION_IDS["那瑪夏區"] == 280


def test_settings_accepts_a_new_kaohsiung_district():
    settings = web_app_v7.load_settings()
    settings["districts"] = ["鳳山區", "仁武區"]

    validated = web_app_v7.previous.previous.validate_settings(settings)

    assert validated["districts"] == ["鳳山區", "仁武區"]


def test_rejected_cards_have_no_misleading_score():
    payload = web_app_v7.load_dashboard_payload()
    card = payload["groups"]["rejected"][0]

    assert card["metric_label"] == "未通過必要條件"
    assert card["metric_value"] is None


def test_stale_cache_is_ignored(tmp_path):
    cache = tmp_path / "cache.json"
    cache.write_text(json.dumps({"A": listing().to_dict()}), encoding="utf-8")
    old = time.time() - web_app_v7.CACHE_TTL_SECONDS - 10
    os.utime(cache, (old, old))
    crawler = web_app_v7.TimedResaleCrawler(
        profile="大樓公寓華廈",
        districts=["楠梓區"],
        cache_path=cache,
        max_pages=3,
    )

    assert crawler._load_cache() == {}
    assert crawler.cache_expired is True


def test_two_missing_full_scans_archive_listing(tmp_path, monkeypatch):
    history = tmp_path / "history.json"
    history.write_text(
        json.dumps({"A": {"search_profile": "大樓公寓華廈"}}), encoding="utf-8"
    )
    monkeypatch.setattr(web_app_v7, "HISTORY_PATH", history)

    first, archived_first = web_app_v7._full_scan_merge(
        [listing()], [], "大樓公寓華廈"
    )
    second, archived_second = web_app_v7._full_scan_merge(
        first, [], "大樓公寓華廈"
    )

    assert len(first) == 1
    assert first[0].lifecycle_status == "possibly_removed"
    assert archived_first == 0
    assert second == []
    assert archived_second == 1


def test_v7_page_loads_region_and_filter_controls():
    page = web_app_v7.app.test_client().get("/").get_data(as_text=True)

    assert "dashboard_v7.js" in page
    assert "dashboard_v7.css" in page


def test_empty_full_scan_preserves_existing_and_miss_count(tmp_path, monkeypatch):
    history = tmp_path / "history.json"
    history.write_text(
        json.dumps({"A": {"missed_full_scans": 1}}), encoding="utf-8"
    )
    monkeypatch.setattr(web_app_v7, "HISTORY_PATH", history)

    merged, archived, reason = web_app_v7._merge_full_scan_safely(
        [listing()], [], "大樓公寓華廈", {"detail_failures": 0}
    )

    assert [item.external_id for item in merged] == ["A"]
    assert archived == 0
    assert reason == "完整盤點未讀取到任何房源"
    saved = json.loads(history.read_text(encoding="utf-8"))
    assert saved["A"]["missed_full_scans"] == 1


def test_all_detail_failures_preserve_unseen_existing_listing():
    failed = listing("B", lifecycle_status="possibly_removed")

    merged, archived, reason = web_app_v7._merge_full_scan_safely(
        [listing()], [failed], "大樓公寓華廈", {"detail_failures": 1}
    )

    assert {item.external_id for item in merged} == {"A", "B"}
    assert archived == 0
    assert reason == "本次讀取的房源詳情全部失敗"


def test_sharp_full_scan_drop_preserves_existing_listings():
    existing = [listing(str(index)) for index in range(8)]
    fetched = [listing("NEW")]

    merged, archived, reason = web_app_v7._merge_full_scan_safely(
        existing, fetched, "大樓公寓華廈", {"detail_failures": 0}
    )

    assert len(merged) == 9
    assert archived == 0
    assert reason == "完整盤點讀取量異常偏低（1/8）"


def test_v7_script_selects_first_non_empty_result_category():
    script = (
        Path(web_app_v7.__file__).with_name("static") / "dashboard_v7.js"
    ).read_text(encoding="utf-8")

    assert "RESULT_STATUS_PRIORITY_V7" in script
    assert "selectFirstNonEmptyStatusV7();" in script


def test_legacy_results_are_re_evaluated_locally(tmp_path, monkeypatch):
    results_path = tmp_path / "current-results.json"
    summary_path = tmp_path / "current-summary.md"
    settings = web_app_v7.load_settings()
    expected = [item.to_dict() for item in evaluate_all([listing()], settings)]
    legacy = [{**expected[0], "status": "rejected", "score": 999}]
    results_path.write_text(json.dumps(legacy, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(web_app_v7.base, "RESULTS_PATH", results_path)
    monkeypatch.setattr(web_app_v7.base, "SUMMARY_PATH", summary_path)
    monkeypatch.setattr(
        web_app_v7,
        "_crawl_for_mode",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("不應重新爬取")
        ),
    )

    payload = web_app_v7.load_dashboard_payload()

    saved = json.loads(results_path.read_text(encoding="utf-8"))
    assert saved["schema_version"] == RESULT_SCHEMA_VERSION
    assert saved["ranking_version"] == RANKING_VERSION
    assert saved["records"] == expected
    assert payload["result_schema_version"] == RESULT_SCHEMA_VERSION
    assert payload["ranking_version"] == RANKING_VERSION


def test_current_results_do_not_trigger_re_evaluation(tmp_path, monkeypatch):
    results_path = tmp_path / "current-results.json"
    summary_path = tmp_path / "current-summary.md"
    records = [
        item.to_dict()
        for item in evaluate_all([listing()], web_app_v7.load_settings())
    ]
    results_path.write_text(
        json.dumps(
            {
                "schema_version": RESULT_SCHEMA_VERSION,
                "ranking_version": RANKING_VERSION,
                "records": records,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(web_app_v7.base, "RESULTS_PATH", results_path)
    monkeypatch.setattr(web_app_v7.base, "SUMMARY_PATH", summary_path)
    monkeypatch.setattr(
        web_app_v7,
        "evaluate_all",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("不應重算")
        ),
    )

    payload = web_app_v7.load_dashboard_payload()

    assert payload["summary"]["total"] == 1
