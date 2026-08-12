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
        {"name": "公司", "address": "高雄市燕巢區義大路1號", "minutes": 25, "distance_km": 18.0},
        {"name": "住家", "address": "高雄市楠梓區常德路333號", "minutes": 10, "distance_km": 6.5},
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


def test_v15_assets_and_launcher_are_active():
    with web_app_v15.app.test_request_context("/"):
        page = web_app_v15.index_v15()
    root = Path(web_app_v15.__file__).parents[2]
    script = (Path(web_app_v15.__file__).with_name("static") / "dashboard_v15.js").read_text(encoding="utf-8")
    assert "/static/dashboard_v15.css" in page
    assert "估算通勤時間" in script
    assert "不含即時路況" in script
    assert "是否同意本次瀏覽期間使用" in script
    assert "home_finder.web_app_v15" in (root / "開啟找房介面.cmd").read_text(encoding="utf-8")
