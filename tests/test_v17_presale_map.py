from pathlib import Path

from home_finder import web_app_v17


def test_v17_loads_presale_discovery_map_assets():
    with web_app_v17.app.test_request_context("/"):
        page = web_app_v17.index_v17()
    assert "leaflet@1.9.4" in page
    assert "/static/dashboard_v17.css" in page
    assert "/static/dashboard_v17.js" in page


def test_presale_map_keeps_incomplete_projects_and_marks_approximate_location():
    static = Path(web_app_v17.__file__).with_name("static")
    script = (static / "dashboard_v17.js").read_text(encoding="utf-8")
    assert 'item.profile !== "預售屋"' in script
    assert '"只有基本資料"' in script
    assert '"部分資訊公開"' in script
    assert '"公開資訊較完整"' in script
    assert "行政區約略位置" in script
    assert "allPresalesV17" in script
