import json

from home_finder.broker_watchlist import broker_alert, load_watchlist, update_watchlist
from home_finder.user_models import HomeListing


def _listing(listing_id: str, warnings: list[str]) -> HomeListing:
    return HomeListing(
        source="591中古屋",
        external_id=listing_id,
        title=f"測試房源 {listing_id}",
        url=f"https://sale.591.com.tw/home/house/detail/2/{listing_id}.html",
        city="高雄市",
        district="楠梓區",
        total_price_wan=1000,
        broker_name="測試地產有限公司",
        data_warnings=warnings,
    )


def test_watchlist_records_evidence_once_and_marks_same_broker(tmp_path):
    path = tmp_path / "broker_watchlist.json"
    flagged = _listing(
        "100",
        ["型態標示 別墅，但樓層為 8 / 15 樓，依集合住宅排除"],
    )
    update_watchlist([flagged], path)
    update_watchlist([flagged], path)

    payload = load_watchlist(path)
    alert = broker_alert("591中古屋", "測試地產有限公司", payload)
    assert alert is not None
    assert alert["incident_count"] == 1
    assert alert["incidents"][0]["listing_id"] == "100"
    assert json.loads(path.read_text(encoding="utf-8"))["version"] == 1


def test_watchlist_does_not_flag_broker_without_structural_conflict(tmp_path):
    path = tmp_path / "broker_watchlist.json"
    update_watchlist([_listing("101", ["屋齡資料不明"])], path)
    assert broker_alert(
        "591中古屋", "測試地產有限公司", load_watchlist(path)
    ) is None
