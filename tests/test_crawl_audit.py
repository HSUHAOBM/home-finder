import json

from home_finder.crawl_audit import append_crawl_audit
from home_finder.user_models import HomeListing


def test_append_crawl_audit_writes_searchable_jsonl(tmp_path):
    path = tmp_path / "crawl_audit.jsonl"
    listing = HomeListing(
        source="591中古屋",
        external_id="20725722",
        title="楓梓楓都夜市、火車站大套房",
        url="https://sale.591.com.tw/home/house/detail/2/20725722.html",
        city="高雄市",
        district="楓梓區",
        total_price_wan=298,
        deal_kind="中古屋",
        property_type="電梯大樓",
    )

    count = append_crawl_audit(
        path,
        [listing],
        profile="大樓公寓華廈",
        mode="daily",
        saved_to="output/current-results.json",
        crawled_at="2026-08-17T07:35:17+00:00",
    )

    record = json.loads(path.read_text(encoding="utf-8").strip())
    assert count == 1
    assert record["external_id"] == "20725722"
    assert record["total_price_wan"] == 298
    assert record["result"] == "stored"
    assert record["saved_to"] == "output/current-results.json"
