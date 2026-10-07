import json

import pytest

from home_finder.crawler_591_multi import MultiPage591ResaleCrawler


def test_invalid_direct_url_records_failed_run(tmp_path):
    path = tmp_path / "trace.jsonl"
    crawler = MultiPage591ResaleCrawler(
        profile="大樓公寓華廈", districts=["橋頭區"], audit_path=path
    )
    with pytest.raises(ValueError):
        crawler.fetch_url("https://example.com/21032611")
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert [record["event"] for record in records] == ["run_started", "run_failed"]
    assert records[0]["run_id"] == records[1]["run_id"]
    assert records[1]["error_type"] == "ValueError"
    crawler._audit("card_parse_failed", external_id="21032611", card={"text": "橋頭測試"})
    assert "橋頭測試" in path.read_text(encoding="utf-8")


def test_unparseable_card_is_logged_with_id_and_original_text(tmp_path):
    path = tmp_path / "trace.jsonl"
    crawler = MultiPage591ResaleCrawler(
        profile="大樓公寓華廈", districts=["橋頭區"], audit_path=path
    )

    class Cards:
        @property
        def first(self):
            return self

        def wait_for(self, **kwargs):
            pass

        def evaluate_all(self, script):
            return [{"href": "/home/house/detail/2/21032611.html",
                     "text": "無法辨認格局的卡片", "title": "橋頭測試"}]

    class Page:
        url = "https://sale.591.com.tw/?regionid=17"

        def locator(self, selector):
            return Cards()

    assert crawler._read_profile_cards(Page()) == []
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert records[0]["raw_count"] == 1
    assert records[1]["event"] == "card_parse_failed"
    assert records[1]["external_id"] == "21032611"
    assert records[1]["card"]["text"] == "無法辨認格局的卡片"
