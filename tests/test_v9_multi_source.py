from __future__ import annotations


from home_finder import web_app_v9
from home_finder.user_models import HomeListing


def listing(source: str, external_id: str) -> HomeListing:
    return HomeListing(
        source=source,
        external_id=external_id,
        title=f"{source} 測試房源",
        url=f"https://example.com/{source}/{external_id}",
        city="高雄市",
        district="三民區",
        total_price_wan=1000,
        property_type="電梯大樓",
    )


def settings() -> dict:
    return {
        "districts": ["三民區", "橋頭區"],
        "search": {
            "pages": 3,
            "publish_days": 5,
            "resale_details": 10,
        },
        "profiles": {"大樓公寓華廈": {"max_price": 1200}},
    }


def test_multi_source_keeps_success_when_yungching_fails(monkeypatch):
    def fake_591(profile, current_settings, source, mode):
        return [listing("591中古屋", "591-1")], {
            "source": "591",
            "fetched": 1,
            "detail_failures": 0,
        }

    class BrokenYungchingCrawler:
        def __init__(self, **kwargs):
            pass

        def fetch(self):
            raise RuntimeError("temporary block")

    monkeypatch.setattr(web_app_v9, "_original_crawl_for_mode", fake_591)
    monkeypatch.setattr(web_app_v9, "BrowserYungchingCrawler", BrokenYungchingCrawler)

    results, diagnostics = web_app_v9._crawl_for_mode_multi(
        "大樓公寓華廈",
        settings(),
        {"yungching_enabled": True, "delay_seconds": 2},
        "daily",
    )

    assert [(item.source, item.external_id) for item in results] == [
        ("591中古屋", "591-1")
    ]
    assert diagnostics["fetched"] == 1
    assert diagnostics["partial_errors"][0].startswith("永慶房仲網：RuntimeError")
    assert web_app_v9._full_scan_archive_skip_reason_multi(
        [], results, "大樓公寓華廈", diagnostics
    ) == "部分來源失敗，避免誤判其他來源已下架"


def test_multi_source_combines_each_source_without_id_collision(monkeypatch):
    shared_id = "12345"

    def fake_591(profile, current_settings, source, mode):
        return [listing("591中古屋", shared_id)], {
            "source": "591",
            "fetched": 1,
            "detail_failures": 0,
        }

    class WorkingYungchingCrawler:
        def __init__(self, **kwargs):
            self.stats = {
                "source": "永慶房仲網",
                "fetched": 1,
                "detail_failures": 0,
            }

        def fetch(self):
            return [listing("永慶房仲網", shared_id)]

    monkeypatch.setattr(web_app_v9, "_original_crawl_for_mode", fake_591)
    monkeypatch.setattr(web_app_v9, "BrowserYungchingCrawler", WorkingYungchingCrawler)

    results, diagnostics = web_app_v9._crawl_for_mode_multi(
        "大樓公寓華廈",
        settings(),
        {"yungching_enabled": True, "delay_seconds": 2},
        "daily",
    )

    assert {(item.source, item.external_id) for item in results} == {
        ("591中古屋", shared_id),
        ("永慶房仲網", shared_id),
    }
    assert diagnostics["partial_errors"] == []
    assert diagnostics["fetched"] == 2
