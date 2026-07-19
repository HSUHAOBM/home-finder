from __future__ import annotations

import os
import re
import threading

import pytest
from playwright.sync_api import expect, sync_playwright
from werkzeug.serving import make_server

from tests.e2e_server import isolated_app


pytestmark = [
    pytest.mark.browser_e2e,
    pytest.mark.skipif(
        os.getenv("RUN_BROWSER_E2E") != "1",
        reason="set RUN_BROWSER_E2E=1 to run the real-browser flow",
    ),
]


def test_dashboard_goal_and_category_flow_in_real_browser(tmp_path):
    with isolated_app(tmp_path) as app:
        server = make_server("127.0.0.1", 0, app, threaded=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base_url = f"http://127.0.0.1:{server.server_port}"
        browser_problems: list[str] = []

        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                page = browser.new_page(viewport={"width": 1440, "height": 1000})
                page.set_default_timeout(5_000)
                page.on(
                    "console",
                    lambda message: (
                        browser_problems.append(
                            f"console {message.type}: {message.text}"
                        )
                        if message.type in {"error", "warning"}
                        else None
                    ),
                )
                page.on(
                    "pageerror",
                    lambda error: browser_problems.append(f"pageerror: {error}"),
                )

                page.goto(base_url, wait_until="networkidle")

                acceptable = page.locator('.tab[data-status="acceptable"]')
                expect(acceptable).to_have_class(re.compile(r"\bactive\b"))
                expect(page.locator("#results")).to_contain_text(
                    "E2E 可接受大樓"
                )

                page.locator('[data-profile="透天別墅"]').click()
                exact = page.locator('.tab[data-status="exact_match"]')
                expect(exact).to_have_class(re.compile(r"\bactive\b"))
                expect(page.locator("#results")).to_contain_text(
                    "E2E 完全符合透天"
                )

                pending = page.locator(
                    '.tab[data-status="needs_verification"]'
                )
                pending.click()
                expect(pending).to_have_class(re.compile(r"\bactive\b"))
                expect(page.locator("#results")).to_contain_text(
                    "目前沒有房源"
                )

                page.locator('[data-profile="預售屋"]').click()
                expect(pending).to_have_class(re.compile(r"\bactive\b"))
                expect(page.locator("#results")).to_contain_text(
                    "E2E 待確認預售"
                )

                page.locator("#selected-settings-button").click()
                dialog = page.locator("#settings-dialog")
                expect(dialog).to_be_visible()
                expect(dialog).to_contain_text("調整目標 03條件")
                page.locator("#settings-close").click()
                expect(dialog).not_to_be_visible()

                browser.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

        assert browser_problems == []
