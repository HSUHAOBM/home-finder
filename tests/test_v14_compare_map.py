from __future__ import annotations

import json
from pathlib import Path

from home_finder import web_app, web_app_v14


def test_dashboard_card_exposes_address():
    record = {
        "listing": {
            "external_id": "map-1", "source": "591中古屋", "title": "地圖房源",
            "url": "https://example.test/map-1", "district": "楠梓區",
            "address": "常德路333號", "total_price_wan": 1000,
        },
        "status": "qualified", "profile": "大樓公寓華廈",
    }
    assert web_app._card(record)["address"] == "常德路333號"


def test_commute_settings_api_reads_local_file(tmp_path: Path, monkeypatch):
    path = tmp_path / "commute.json"
    path.write_text(json.dumps({"destinations": [{"name": "公司", "address": "義大路1號"}]}), encoding="utf-8")
    monkeypatch.setattr(web_app_v14, "COMMUTE_SETTINGS_PATH", path)
    response = web_app_v14.app.test_client().get("/api/commute-settings")
    assert response.status_code == 200
    assert response.get_json()["destinations"][0]["name"] == "公司"


def test_v14_assets_launcher_and_features():
    with web_app_v14.app.test_request_context("/"):
        page = web_app_v14.index_v14()
    root = Path(web_app_v14.__file__).parents[2]
    static = Path(web_app_v14.__file__).with_name("static")
    script = (static / "dashboard_v14.js").read_text(encoding="utf-8")
    assert "/static/dashboard_v14.css" in page
    assert "favorite-compare-open" in script
    assert "favorite-map-button" in script
    assert "travelmode" in script
    assert "一次最多比較 4 間收藏" in script
    assert "home_finder.web_app_v14" in (root / "開啟找房介面.cmd").read_text(encoding="utf-8")
