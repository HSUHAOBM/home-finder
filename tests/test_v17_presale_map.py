from pathlib import Path

from home_finder import web_app_v17


def test_v17_loads_presale_discovery_map_assets():
    with web_app_v17.app.test_request_context("/"):
        page = web_app_v17.index_v17()
    assert "leaflet@1.9.4" in page
    assert "/static/dashboard_v17.css" in page
    assert "/static/dashboard_v17.js" in page


def test_property_map_opens_as_standalone_page_with_rich_detail():
    response = web_app_v17.app.test_client().get(
        "/property-map?profile=大樓公寓華廈&status=near_match"
    )
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert 'id="property-map"' in page
    assert 'id="map-status-tabs"' in page
    assert 'data-status="acceptable"' in page
    assert 'data-status="rejected"' in page
    assert 'data-status="favorites"' in page
    assert 'window.INITIAL_MAP_STATUS = "near_match"' in page
    assert 'id="map-sort"' in page
    assert 'id="map-failure"' in page
    assert "/static/property_map.js" in page
    static = Path(web_app_v17.__file__).with_name("static")
    script = (static / "property_map.js").read_text(encoding="utf-8")
    assert "price_per_total_area" in script
    assert "price_per_main_area" in script
    assert "開啟原始房源" in script
    assert "loadStatus" in script
    assert "failureCategories" in script
    assert "sortedItems" in script
    assert 'status === "favorites"' in script
    assert "focusMarker" in script
    assert "marker.closeTooltip()" in script
    assert "state.map.flyTo" in script
    assert "price_per_total_area" in script
    assert "hiddenMapNotes" in script
    assert "location-note" not in script


def test_presale_map_keeps_incomplete_projects_and_marks_approximate_location():
    static = Path(web_app_v17.__file__).with_name("static")
    script = (static / "dashboard_v17.js").read_text(encoding="utf-8")
    assert 'item.profile !== "預售屋"' in script
    assert '"只有基本資料"' in script
    assert '"部分資訊公開"' in script
    assert '"公開資訊較完整"' in script
    assert "行政區約略位置" in script
    assert "allPresalesV17" in script
