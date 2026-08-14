from __future__ import annotations

from pathlib import Path

from home_finder.commute_estimator import estimate_commute
from home_finder import web_app_v15


def test_estimate_geocodes_then_uses_single_route_table_request(tmp_path):
    calls = []
    geocodes = iter([
        [{"lat": "22.72", "lon": "120.33"}],
        [{"lat": "22.76", "lon": "120.36"}],
        [{"lat": "22.73", "lon": "120.32"}],
    ])

    def fake_get(url):
        calls.append(url)
        if "nominatim" in url:
            return next(geocodes)
        return {"code": "Ok", "durations": [[1500, 600]], "distances": [[18000, 6500]]}

    result = estimate_commute(
        "高雄市楠梓區測試路1號",
        [{"name": "公司", "address": "高雄市燕巢區義大路1號"}, {"name": "住家", "address": "高雄市楠梓區常德路333號"}],
        cache_path=tmp_path / "commute.json", get_json=fake_get, sleep=lambda _: None,
    )
    assert result["estimates"] == [
        {"name": "公司", "address": "高雄市燕巢區義大路1號", "resolved_address": "高雄市燕巢區義大路1號", "minutes": 25, "distance_km": 18.0},
        {"name": "住家", "address": "高雄市楠梓區常德路333號", "resolved_address": "高雄市楠梓區常德路333號", "minutes": 10, "distance_km": 6.5},
    ]
    assert len([url for url in calls if "table/v1/driving" in url]) == 1

    calls.clear()
    cached = estimate_commute(
        "高雄市楠梓區測試路1號",
        [{"name": "公司", "address": "高雄市燕巢區義大路1號"}, {"name": "住家", "address": "高雄市楠梓區常德路333號"}],
        cache_path=tmp_path / "commute.json", get_json=fake_get, sleep=lambda _: None,
    )
    assert cached["cached"] is True
    assert calls == []


def test_estimate_falls_back_from_community_to_road(tmp_path):
    calls = []

    def fake_get(url):
        calls.append(url)
        if "nominatim" in url:
            if "%E5%87%BD%E5%AE%87-%E6%B0%B4%E6%82%85" in url:
                return []
            return [{"lat": "22.70", "lon": "120.35"}]
        return {"code": "Ok", "durations": [[1200]], "distances": [[15000]]}

    result = estimate_commute(
        "高雄市仁武區 函宇-水悅",
        [{"name": "公司", "address": "高雄市燕巢區義大路1號"}],
        cache_path=tmp_path / "commute.json",
        origin_fallbacks=["高雄市仁武區八德北路"],
        get_json=fake_get, sleep=lambda _: None,
    )
    assert result["resolved_origin"] == "高雄市仁武區八德北路"
    assert result["estimates"][0]["minutes"] == 20
    assert len([url for url in calls if "nominatim" in url]) == 3


def test_estimate_falls_back_from_village_address_to_landmark(tmp_path):
    calls = []

    def fake_get(url):
        calls.append(url)
        if "nominatim" in url:
            if "%E8%A7%92%E5%AE%BF%E9%87%8C" in url:
                return []
            return [{"lat": "22.76", "lon": "120.36"}]
        return {"code": "Ok", "durations": [[1500]], "distances": [[18000]]}

    result = estimate_commute(
        "高雄市仁武區八德北路",
        [{"name": "公司・義大醫院", "address": "高雄市燕巢區角宿里義大路1號"}],
        cache_path=tmp_path / "commute.json", get_json=fake_get, sleep=lambda _: None,
    )
    estimate = result["estimates"][0]
    assert estimate["resolved_address"] == "高雄市燕巢區義大路1號"
    assert estimate["minutes"] == 25
    assert any("%E7%BE%A9%E5%A4%A7%E8%B7%AF1%E8%99%9F" in url for url in calls)


def test_v15_removes_osrm_ui_and_api_but_keeps_launcher_compatible():
    with web_app_v15.app.test_request_context("/"):
        page = web_app_v15.index_v15()
    root = Path(web_app_v15.__file__).parents[2]
    assert "/static/dashboard_v15.css" not in page
    assert "/static/dashboard_v15.js" not in page
    assert web_app_v15.app.test_client().post("/api/commute-estimate", json={}).status_code == 404
    assert "home_finder.web_app_v16" in (root / "開啟找房介面.cmd").read_text(encoding="utf-8")
