from __future__ import annotations

from playwright.sync_api import Page

from .crawler_591_browser import Browser591Crawler as _Browser591Crawler


class Browser591Crawler(_Browser591Crawler):
    """591 crawler with visible district-button interaction."""

    def _select_districts(self, page: Page) -> None:
        for district in self.districts:
            button = page.get_by_role("button", name=district, exact=True)
            if button.count():
                button.first.click()
                page.wait_for_timeout(700)
        page.wait_for_timeout(3000)
