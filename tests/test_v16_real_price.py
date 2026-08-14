from __future__ import annotations

import csv
import io
import zipfile
from datetime import date
from pathlib import Path

from home_finder import web_app_v16
from home_finder.real_price import KAOHSIUNG_CSV, _rank_record, _recent_seasons, query_real_price


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
    search_mode_script = (root / "src/home_finder/static/dashboard_v6.js").read_text(encoding="utf-8")
    assert 'value="days_7"' in search_mode_script
    assert 'value="days_10"' in search_mode_script
    assert 'value="days_15"' in search_mode_script
    assert "每日更新（不限刊登時間" in search_mode_script
    result_search_script = (root / "src/home_finder/static/dashboard_v10.js").read_text(encoding="utf-8")
    assert "variant.id, variant.title" in result_search_script
    assert "同路段參考" not in script
    assert "home_finder.web_app_v16" in (root / "開啟找房介面.cmd").read_text(encoding="utf-8")
    response = web_app_v16.app.test_client().post("/api/favorites/real-price", json={"source": "591中古屋", "id": "missing", "months": 24})
    assert response.status_code == 400


def test_recent_seasons_uses_four_completed_quarters():
    assert _recent_seasons(date(2026, 8, 12)) == ("114S3", "114S4", "115S1", "115S2")
    assert _recent_seasons(date(2027, 1, 2)) == ("115S1", "115S2", "115S3", "115S4")
    assert len(_recent_seasons(date(2026, 8, 12), 60)) == 20
    assert len(_recent_seasons(date(2026, 8, 12), 120)) == 40
