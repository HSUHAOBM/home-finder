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


def test_settings_save_button_discloses_progress_and_saved_district_count():
    root = Path(web_app_v7.__file__).parent
    script = (root / "static" / "dashboard_v3.js").read_text(encoding="utf-8")

    assert "儲存中…" in script
    assert "已儲存 ${payload.settings.districts.length} 區 ✓" in script


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


def test_daily_search_marks_unseen_listings_in_same_profile_only():
    old = listing("old", lifecycle_status="updated")
    current = listing("current", lifecycle_status="seen")
    other_profile = listing(
        "house", search_profile="透天別墅", property_type="透天厝"
    )

    marked = web_app_v7._mark_unseen_daily_listings(
        [old, current, other_profile], [listing("current")], "大樓公寓華廈"
    )

    assert old.lifecycle_status == "not_seen"
    assert "網址尚未確認是否下架" in old.data_warnings[0]
    assert current.lifecycle_status == "seen"
    assert other_profile.lifecycle_status is None


def test_daily_search_does_not_mark_anything_when_source_returned_nothing():
    old = listing("old", lifecycle_status="updated")

    marked = web_app_v7._mark_unseen_daily_listings(
        [old], [], "大樓公寓華廈"
    )

    assert marked[0].lifecycle_status == "updated"


def test_fetched_listing_refreshes_cached_url_status(tmp_path):
    path = tmp_path / "url-availability.json"
    path.write_text(
        json.dumps({
            "591中古屋:A": {
                "url_availability_status": "removed",
                "url_availability_reason": "網址回傳 HTTP 404",
            }
        }, ensure_ascii=False),
        encoding="utf-8",
    )

    web_app_v7._record_fetched_availability(
        [listing("A")], path, checked_at="2026-09-09T03:00:00+08:00"
    )

    saved = json.loads(path.read_text(encoding="utf-8"))["591中古屋:A"]
    assert saved["url_availability_status"] == "available"
    assert saved["url_availability_reason"] == "本次爬蟲已找到"


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


def test_unexpected_results_failure_returns_json(monkeypatch):
    def fail_to_load():
        raise RuntimeError("simulated stale service failure")

    monkeypatch.setattr(web_app_v7, "load_dashboard_payload", fail_to_load)

    response = web_app_v7.app.test_client().get("/api/results")

    assert response.status_code == 500
    assert response.is_json
    assert (
        response.get_json()["error"]
        == "結果服務發生未預期錯誤，請關閉舊的命令視窗，再重新開啟找房介面。"
    )

def test_successful_crawl_history_is_persisted_and_exposed(tmp_path, monkeypatch):
    history_path = tmp_path / "search-history.json"
    diagnostics_path = tmp_path / "diagnostics.json"
    timestamps = iter(
        ["2026-07-24T01:02:03+00:00", "2026-07-25T04:05:06+00:00"]
    )
    monkeypatch.setattr(web_app_v7, "SEARCH_HISTORY_PATH", history_path)
    monkeypatch.setattr(web_app_v7, "DIAGNOSTICS_PATH", diagnostics_path)
    monkeypatch.setattr(web_app_v7.base, "_iso_now", lambda: next(timestamps))

    first = web_app_v7._record_successful_crawl(
        "大樓公寓華廈",
        "daily",
        {"fetched": 18, "duration_seconds": 103.8, "district_count": 4},
    )
    second = web_app_v7._record_successful_crawl(
        "預售屋",
        "full",
        {"fetched": 9, "duration_seconds": 88.2, "district_count": 4},
    )
    payload = web_app_v7.build_dashboard_payload([])

    assert json.loads(history_path.read_text(encoding="utf-8")) == [first, second]
    assert payload["last_successful_crawl"] == second
    assert payload["successful_crawls_by_profile"]["大樓公寓華廈"] == first
    assert payload["crawl_history"] == [first, second]


def test_failed_search_does_not_record_success(tmp_path, monkeypatch):
    history_path = tmp_path / "search-history.json"
    original_state = web_app_v7.base._state_snapshot()
    monkeypatch.setattr(web_app_v7, "SEARCH_HISTORY_PATH", history_path)
    monkeypatch.setattr(
        web_app_v7,
        "_crawl_for_mode",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("抓取失敗")),
    )

    try:
        web_app_v7._run_search("大樓公寓華廈", "daily")
        assert not history_path.exists()
        state = web_app_v7.base._state_snapshot()
        assert state["phase"] == "error"
        assert state["duration_seconds"] >= 0
    finally:
        with web_app_v7.base._state_lock:
            web_app_v7.base._state.clear()
            web_app_v7.base._state.update(original_state)


def test_ui_displays_successful_crawl_time():
    static_dir = Path(web_app_v7.__file__).with_name("static")
    dashboard = (static_dir / "dashboard_v3.js").read_text(encoding="utf-8")
    dashboard_v7 = (static_dir / "dashboard_v7.js").read_text(encoding="utf-8")

    assert "最近成功爬蟲" in dashboard
    assert "last_successful_crawl" in dashboard
    assert "formatDuration" in dashboard
    assert "・耗時 ${duration}" in dashboard
    assert "successful_crawls_by_profile" in dashboard_v7
    assert "最近成功 ${successTime}" in dashboard_v7


def test_ui_anchors_relative_591_update_text_and_marks_stale_cards():
    static_dir = Path(web_app_v7.__file__).with_name("static")
    dashboard_v4 = (static_dir / "dashboard_v4.js").read_text(encoding="utf-8")
    dashboard_v7 = (static_dir / "dashboard_v7.js").read_text(encoding="utf-8")

    assert "舊資料・未重新確認" in dashboard_v4
    assert "本輪列表未收錄" in dashboard_v4
    assert "抓取時，591 顯示" in dashboard_v4
    assert "最後確認：" in dashboard_v4
    assert "&& !isTrackingStale(item)" in dashboard_v7

def test_status_polling_only_runs_while_search_is_active():
    script = (
        Path(web_app_v7.__file__).with_name("static") / "dashboard_v3.js"
    ).read_text(encoding="utf-8")

    assert "setInterval(pollStatus" not in script
    assert "scheduleStatusPoll(delay = 2500)" in script
    assert "if (state.searchRunning) scheduleStatusPoll()" in script
    assert 'document.addEventListener("visibilitychange"' in script
    assert 'window.addEventListener("focus"' in script

def test_development_launcher_reloads_service_and_browser_after_file_changes():
    project_dir = Path(web_app_v7.__file__).resolve().parents[2]
    base_source = (Path(web_app_v7.__file__).with_name("web_app.py")).read_text(
        encoding="utf-8"
    )
    script = (
        Path(web_app_v7.__file__).with_name("static") / "dashboard_v3.js"
    ).read_text(encoding="utf-8")
    launcher = (project_dir / "開啟找房介面.cmd").read_text(encoding="utf-8")

    assert "use_reloader=args.reload" in base_source
    assert "extra_files=_reload_extra_files() if args.reload else None" in base_source
    assert "status.service_instance !== state.serviceInstance" in script
    assert "window.location.reload()" in script
    assert "--reload" in launcher


def test_v7_script_supports_total_and_main_area_unit_price_sorting():
    script = (
        Path(web_app_v7.__file__).with_name("static") / "dashboard_v7.js"
    ).read_text(encoding="utf-8")

    assert 'value="total-unit-asc"' in script
    assert 'value="total-unit-desc"' in script
    assert 'value="main-unit-asc"' in script
    assert 'value="main-unit-desc"' in script
    assert 'numericSort("price_per_total_area")' in script
    assert 'numericSort("price_per_main_area")' in script
    assert "firstMissing ? 1 : -1" in script
    assert 'data-sort-field="age"' in script
    assert 'if (mode === "age-asc")' in script
    assert 'if (mode === "age-desc")' in script
    assert 'data-sort-field="total-unit"' in script
    assert 'data-sort-field="main-unit"' in script
    assert 'data-sort-field="failures"' in script
    assert '>不符合項目</button>' in script
    assert 'data-sort-field="metric">推薦' not in script
    assert 'return "無車位"' in script
    assert 'return "非平面車位"' in script
    assert '["near_match", "rejected"].includes(state.activeStatus)' in script
    assert "syncSortButtonsV7" in script


def test_v7_assets_support_persistent_compact_and_comfortable_cards():
    static_dir = Path(web_app_v7.__file__).with_name("static")
    script = (static_dir / "dashboard_v7.js").read_text(encoding="utf-8")
    styles = (static_dir / "dashboard_v7.css").read_text(encoding="utf-8")
    dashboard = (static_dir / "dashboard_v3.js").read_text(encoding="utf-8")

    assert 'data-view-mode="comfortable"' in script
    assert 'data-view-mode="compact"' in script
    assert "home-finder-result-view-mode" in script
    assert 'classList.toggle("compact-view"' in script
    assert ".results.compact-view" in styles
    assert "status-${escapeHtml(item.status)}" in dashboard
