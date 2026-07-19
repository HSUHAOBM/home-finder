from pathlib import Path

import pytest

from home_finder import crawler_591_browser


class FakePlaywright:
    def __enter__(self):
        return object()

    def __exit__(self, exc_type, exc_value, traceback):
        return False


class FailingPage:
    def goto(self, *args, **kwargs):
        raise RuntimeError("simulated crawl failure")


class FakeContext:
    def new_page(self):
        return FailingPage()


class FakeBrowser:
    def __init__(self):
        self.connected = True
        self.closed = False

    def new_context(self, **kwargs):
        return FakeContext()

    def is_connected(self):
        return self.connected

    def close(self):
        self.connected = False
        self.closed = True


def test_browser_is_closed_when_crawl_raises(monkeypatch, tmp_path):
    browser = FakeBrowser()
    crawler = crawler_591_browser.Browser591Crawler(
        districts=["左營區"],
        max_details=1,
        delay_seconds=2,
        cache_path=tmp_path / "cache.json",
        sleep=lambda _seconds: None,
    )
    monkeypatch.setattr(crawler_591_browser, "sync_playwright", FakePlaywright)
    monkeypatch.setattr(crawler, "_launch", lambda _playwright: browser)

    with pytest.raises(RuntimeError, match="simulated crawl failure"):
        crawler.fetch()

    assert browser.closed is True


@pytest.mark.parametrize(
    "relative_path",
    [
        "src/home_finder/crawler_591_browser.py",
        "src/home_finder/crawler_591_presale.py",
        "src/home_finder/crawler_591_multi.py",
        "src/home_finder/crawler_591_presale_multi.py",
    ],
)
def test_every_browser_crawler_registers_exception_cleanup(relative_path):
    root = Path(__file__).resolve().parents[1]
    content = (root / relative_path).read_text(encoding="utf-8")

    assert "ExitStack() as cleanup" in content
    assert "cleanup.callback(lambda: browser.is_connected() and browser.close())" in content
