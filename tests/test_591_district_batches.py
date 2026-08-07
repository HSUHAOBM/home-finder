from __future__ import annotations

from home_finder.crawler_591_multi import MultiPage591ResaleCrawler
from home_finder.user_models import HomeListing


def crawler(districts: list[str]) -> MultiPage591ResaleCrawler:
    return MultiPage591ResaleCrawler(
        profile="大樓公寓華廈",
        districts=districts,
        max_pages=3,
        publish_days=5,
        max_details=50,
        delay_seconds=2,
        sleep=lambda _seconds: None,
    )


def listing(external_id: str, district: str) -> HomeListing:
    return HomeListing(
        source="591中古屋",
        external_id=external_id,
        title=f"房源 {external_id}",
        url=f"https://sale.591.com.tw/home/house/detail/2/{external_id}.html",
        city="高雄市",
        district=district,
        total_price_wan=1000,
        property_type="電梯大樓",
        rooms=2,
        living_rooms=1,
        baths=2,
        search_profile="大樓公寓華廈",
    )


def test_each_district_uses_an_independent_search():
    districts = ["三民區", "左營區", "楠梓區", "橋頭區", "仁武區", "大社區"]

    assert crawler(districts)._district_batches() == [
        ["三民區"],
        ["左營區"],
        ["楠梓區"],
        ["橋頭區"],
        ["仁武區"],
        ["大社區"],
    ]


def test_all_districts_are_preserved_as_single_district_queries():
    districts = [f"行政區{index}" for index in range(38)]
    batches = crawler(districts)._district_batches()

    assert len(batches) == 38
    assert all(len(batch) == 1 for batch in batches)
    assert [district for batch in batches for district in batch] == districts


def test_collect_candidates_fetches_every_district_and_interleaves_results(monkeypatch):
    districts = ["三民區", "左營區", "楠梓區"]
    subject = crawler(districts)
    calls: list[list[str]] = []

    def fake_fetch(_context, batch):
        calls.append(batch)
        if batch[0] == "三民區":
            return [listing("A", "三民區"), listing("DUP", "三民區")]
        if batch[0] == "左營區":
            return [listing("B", "左營區"), listing("DUP", "左營區")]
        return [listing("C", "楠梓區")]

    monkeypatch.setattr(subject, "_fetch_batch_candidates", fake_fetch)

    results = subject._collect_candidates(object())

    assert calls == [["三民區"], ["左營區"], ["楠梓區"]]
    assert [item.external_id for item in results] == ["A", "B", "C", "DUP"]
