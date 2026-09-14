from __future__ import annotations

import csv
import io
import json
import zipfile
from datetime import date
from pathlib import Path

from home_finder import real_price, web_app_v16
from home_finder.favorite_availability import AvailabilityResult
from home_finder.real_price import KAOHSIUNG_CSV, _rank_record, _recent_seasons, query_real_price
from home_finder.result_store import read_result_records, write_result_records


def _official_zip(path: Path, rows: list[dict[str, str]]) -> None:
    fields = [
        "鄉鎮市區", "交易標的", "土地位置建物門牌", "交易年月日", "移轉層次",
        "建物型態", "建物移轉總面積平方公尺", "建物現況格局-房", "總價元",
        "單價元平方公尺", "車位類別", "備註", "總樓層數", "建築完成年月",
    ]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(KAOHSIUNG_CSV, output.getvalue())


def test_query_prefers_matching_doorplate_and_summarizes(tmp_path: Path):
    rows = [
        {"鄉鎮市區": "楠梓區", "交易標的": "房地(土地+建物)+車位", "土地位置建物門牌": "常德路331~360號", "交易年月日": "1150501", "移轉層次": "八層", "建物型態": "住宅大樓", "建物移轉總面積平方公尺": "99.17", "建物現況格局-房": "3", "總價元": "10000000", "單價元平方公尺": "100837", "車位類別": "坡道平面", "備註": ""},
        {"鄉鎮市區": "楠梓區", "交易標的": "房地(土地+建物)", "土地位置建物門牌": "常德路100號", "交易年月日": "1150401", "移轉層次": "五層", "建物型態": "華廈", "建物移轉總面積平方公尺": "90", "建物現況格局-房": "3", "總價元": "8000000", "單價元平方公尺": "88888", "車位類別": "", "備註": ""},
    ]
    for season in ("114S3", "114S4", "115S1", "115S2"):
        _official_zip(tmp_path / f"official-{season}.zip", rows)
    result = query_real_price(
        {"district": "楠梓區", "address": "常德路333號", "community": "測試社區", "price": 1080, "total_area": 30, "rooms": 3},
        cache_dir=tmp_path, months=12, today=date(2026, 8, 12),
    )
    assert result["match_level"] == "address"
    assert result["summary"]["count"] == 4
    assert result["transactions"][0]["address"] == "常德路331~360號"
    assert result["listing_unit_price"] == 36
    assert result["comparison_scope"] == "依門牌、權狀坪數、樓層、總樓層、屋齡、房數與車位綜合排序"


def test_city_and_district_prefix_do_not_break_road_matching(tmp_path: Path):
    rows = [{"鄉鎮市區": "楠梓區", "交易標的": "房地(土地+建物)", "土地位置建物門牌": "高雄大學路101號", "交易年月日": "1150501", "移轉層次": "八層", "建物型態": "住宅大樓", "建物移轉總面積平方公尺": "100", "建物現況格局-房": "3", "總價元": "10000000", "單價元平方公尺": "100000", "車位類別": "坡道平面", "備註": ""}]
    for season in ("114S3", "114S4", "115S1", "115S2"):
        _official_zip(tmp_path / f"official-{season}.zip", rows)
    result = query_real_price(
        {"district": "楠梓區", "address": "高雄市楠梓區高雄大學路", "community": "冠藝大廈"},
        cache_dir=tmp_path, today=date(2026, 8, 12),
    )
    assert result["road"] == "高雄大學路"
    assert result["match_level"] == "road"


def test_query_prefers_community_before_address(tmp_path: Path, monkeypatch):
    records = [
        {
            "date": "2026-01-01", "district": "大社區", "address": "三民路1~30號",
            "note": "綠波庭大廈", "total_price_wan": 938, "unit_price_wan_ping": 20.8,
            "area_ping": 45.14, "floor": "六層", "floor_number": 6, "total_floors": 7,
            "building_type": "華廈", "rooms": 4, "completion_year": 1998, "parking": "坡道平面",
        },
        {
            "date": "2026-06-01", "district": "大社區", "address": "三民路62號",
            "note": "其他社區", "total_price_wan": 900, "unit_price_wan_ping": 21,
            "area_ping": 45.14, "floor": "六層", "floor_number": 6, "total_floors": 7,
            "building_type": "華廈", "rooms": 4, "completion_year": 1998, "parking": "坡道平面",
        },
    ]
    monkeypatch.setattr(real_price, "_load_season", lambda _path: records)
    for season in ("114S3", "114S4", "115S1", "115S2"):
        (tmp_path / f"official-{season}.zip").touch()

    result = query_real_price(
        {
            "district": "大社區", "address": "高雄市大社區三民路62號",
            "community": "綠波庭大廈", "price": 938, "total_area": 45.14,
            "rooms": 4, "floor": 6, "total_floors": 7, "age": 28,
            "parking": "坡道平面", "property_type": "華廈",
        },
        cache_dir=tmp_path, today=date(2026, 8, 18),
    )

    assert result["match_level"] == "community"
    assert result["match_label"] == "社區名稱吻合"
    assert result["summary"]["count"] == 4
    assert {item["note"] for item in result["transactions"]} == {"綠波庭大廈"}
    assert result["comparison_scope"].startswith("同社區優先")


def test_similarity_ranks_same_building_signals_before_newer_but_different_transaction(tmp_path: Path):
    rows = [
        {"鄉鎮市區": "楠梓區", "交易標的": "房地(土地+建物)+車位", "土地位置建物門牌": "高楠公路1749號", "交易年月日": "1141001", "移轉層次": "八層", "總樓層數": "九層", "建築完成年月": "0830101", "建物型態": "住宅大樓", "建物移轉總面積平方公尺": "112", "建物現況格局-房": "2", "總價元": "7600000", "單價元平方公尺": "67857", "車位類別": "坡道平面", "備註": "小康成家"},
        {"鄉鎮市區": "楠梓區", "交易標的": "房地(土地+建物)", "土地位置建物門牌": "高楠公路1800號", "交易年月日": "1150501", "移轉層次": "二層", "總樓層數": "十五層", "建築完成年月": "1100101", "建物型態": "住宅大樓", "建物移轉總面積平方公尺": "200", "建物現況格局-房": "4", "總價元": "15000000", "單價元平方公尺": "75000", "車位類別": "無", "備註": ""},
    ]
    for season in ("114S3", "114S4", "115S1", "115S2"):
        _official_zip(tmp_path / f"official-{season}.zip", rows)
    result = query_real_price(
        {"district": "楠梓區", "address": "高雄市楠梓區高楠公路1749號", "community": "小康成家", "total_area": 34.71, "rooms": 2, "floor": 9, "total_floors": 9, "age": 32, "parking": "平面式", "property_type": "電梯大樓"},
        cache_dir=tmp_path, today=date(2026, 8, 12),
    )
    best = result["closest_matches"][0]
    assert best["address"] == "高楠公路1749號"
    assert best["similarity_score"] >= 85
    assert best["similarity_label"] in ("極可能同一棟", "可能同一棟")
    assert "門牌範圍吻合" in best["similarity_reasons"] or "社區名稱吻合" in best["similarity_reasons"]


def test_similarity_marks_probable_favorite_listing_and_ages_transaction_to_query_date(tmp_path: Path):
    best = _rank_record(
        {"date": "2021-05-01", "address": "常德路331~360號", "note": "", "area_ping": 30.0, "rooms": 3, "floor_number": 8, "total_floors": 15, "completion_year": 2016, "parking": "坡道平面", "building_type": "住宅大樓"},
        {"district": "楠梓區", "address": "常德路333號", "price": 1080, "total_area": 30, "rooms": 3, "floor": 8, "total_floors": 15, "age": 10, "parking": "平面式", "property_type": "住宅大樓"},
        date(2026, 8, 12),
    )
    assert best["age_at_query"] == 10
    assert best["similarity_score"] >= 90
    assert best["similarity_label"] == "可能為本收藏房"


def test_v16_assets_launcher_and_api_validation():
    with web_app_v16.app.test_request_context("/"):
        page = web_app_v16.index_v16()
    root = Path(web_app_v16.__file__).parents[2]
    script = (Path(web_app_v16.__file__).with_name("static") / "dashboard_v16.js").read_text(encoding="utf-8")
    assert "/static/dashboard_v16.css" in page
    assert "社區實價" in script
    assert "目前收藏房源" in script
    assert "可能為本收藏房" in script
    assert "data-house-type=\"透天厝\"" in script
    assert "data-house-type=\"別墅\"" in script
    assert "broker_watch_alert" in script
    assert "房仲刊登提醒" in script
    assert 'if (!checked) return ""' in script
    assert 'class="listing-availability-check"' not in script
    assert "/api/listing-availability" not in script
    search_mode_script = (root / "src/home_finder/static/dashboard_v6.js").read_text(encoding="utf-8")
    assert 'value="days_7"' in search_mode_script
    assert 'value="days_10"' in search_mode_script
    assert 'value="days_15"' in search_mode_script
    assert "每日更新（不限刊登時間" in search_mode_script
    result_search_script = (root / "src/home_finder/static/dashboard_v10.js").read_text(encoding="utf-8")
    assert "variant.id, variant.title" in result_search_script
    assert "同路段參考" not in script
    assert "home_finder.web_app_v17" in (root / "開啟找房介面.cmd").read_text(encoding="utf-8")
    response = web_app_v16.app.test_client().post("/api/favorites/real-price", json={"source": "591中古屋", "id": "missing", "months": 24})
    assert response.status_code == 400


def test_listing_availability_returns_separate_url_status(monkeypatch):
    class FakeChecker:
        def check_many(self, items, *, on_result):
            on_result(items[0], AvailabilityResult("removed", "網址回傳 HTTP 404"))

    monkeypatch.setattr(
        web_app_v16.base, "_iso_now", lambda: "2026-09-09T01:02:03+08:00"
    )
    result = web_app_v16.check_listing_availability(
        {"url": "https://example.test/404"}, checker=FakeChecker()
    )

    assert result == {
        "url_availability_status": "removed",
        "url_availability_reason": "網址回傳 HTTP 404",
        "url_availability_checked_at": "2026-09-09T01:02:03+08:00",
    }


def test_listing_availability_api_checks_known_card_and_persists(tmp_path, monkeypatch):
    cache_path = tmp_path / "url-availability.json"
    monkeypatch.setattr(web_app_v16, "URL_AVAILABILITY_PATH", cache_path)
    monkeypatch.setattr(
        web_app_v16,
        "load_dashboard_payload_v16",
        lambda: {
            "groups": {
                "acceptable": [{
                    "source": "591中古屋", "id": "A",
                    "url": "https://example.test/A",
                }]
            }
        },
    )
    monkeypatch.setattr(
        web_app_v16,
        "check_listing_availability",
        lambda _item: {
            "url_availability_status": "available",
            "url_availability_reason": "網址目前可正常開啟",
            "url_availability_checked_at": "2026-09-09T02:00:00+08:00",
        },
    )

    response = web_app_v16.app.test_client().post(
        "/api/listing-availability", json={"source": "591中古屋", "id": "A"}
    )

    assert response.status_code == 200
    assert response.get_json()["url_availability_status"] == "available"
    saved = json.loads(cache_path.read_text(encoding="utf-8"))
    assert saved["591中古屋:A"]["url_availability_reason"] == "網址目前可正常開啟"


def test_delete_api_removes_only_requested_removed_card_and_keeps_history(tmp_path, monkeypatch):
    results_path = tmp_path / "current-results.json"
    summary_path = tmp_path / "summary.md"
    favorites_path = tmp_path / "favorites.json"
    deleted_path = tmp_path / "deleted.json"
    records = [
        {"listing": {"source": "591中古屋", "external_id": value}, "profile": "大樓公寓華廈"}
        for value in ("removed", "available")
    ]
    write_result_records(results_path, records)
    favorites_path.write_text(
        json.dumps({"version": 2, "items": []}, ensure_ascii=False), encoding="utf-8"
    )
    payload = {
        "groups": {
            "exact_match": [
                {
                    "source": "591中古屋", "id": "removed", "title": "已下架",
                    "profile": "大樓公寓華廈", "status": "exact_match",
                    "url_availability_status": "removed", "variants": [],
                },
                {
                    "source": "591中古屋", "id": "available", "title": "刊登中",
                    "profile": "大樓公寓華廈", "status": "exact_match",
                    "url_availability_status": "available", "variants": [],
                },
            ]
        },
        "favorites": [],
    }
    monkeypatch.setattr(web_app_v16.base, "RESULTS_PATH", results_path)
    monkeypatch.setattr(web_app_v16.base, "SUMMARY_PATH", summary_path)
    monkeypatch.setattr(web_app_v16.favorites_app, "FAVORITES_PATH", favorites_path)
    monkeypatch.setattr(web_app_v16, "DELETED_LISTINGS_PATH", deleted_path)
    monkeypatch.setattr(web_app_v16, "load_dashboard_payload_v16", lambda: payload)
    monkeypatch.setattr(
        web_app_v16.crawl_app.previous,
        "_write_results",
        lambda remaining: write_result_records(results_path, remaining),
    )

    response = web_app_v16.app.test_client().post(
        "/api/listings/delete",
        json={
            "items": [{"source": "591中古屋", "id": "removed"}],
            "profile": "大樓公寓華廈",
            "category": "exact_match",
            "removed_only": True,
        },
    )

    assert response.status_code == 200
    assert response.get_json()["deleted"] == 1
    assert [item["listing"]["external_id"] for item in read_result_records(results_path)] == ["available"]
    tombstone = json.loads(deleted_path.read_text(encoding="utf-8"))["items"]
    assert tombstone["591中古屋:removed"]["state"] == "deleted"


def test_recent_seasons_uses_four_completed_quarters():
    assert _recent_seasons(date(2026, 8, 12)) == ("114S3", "114S4", "115S1", "115S2")
    assert _recent_seasons(date(2027, 1, 2)) == ("115S1", "115S2", "115S3", "115S4")
    assert len(_recent_seasons(date(2026, 8, 12), 60)) == 20
    assert len(_recent_seasons(date(2026, 8, 12), 120)) == 40
