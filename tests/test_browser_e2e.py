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
                expect(page.locator(".listing-import-panel")).to_be_visible()
                mortgage_button = page.locator("#mortgage-calculator-button")
                expect(mortgage_button).to_be_visible()
                mortgage_button.click()
                mortgage_dialog = page.locator("#mortgage-dialog")
                expect(mortgage_dialog).to_be_visible()
                page.locator("#mortgage-price").fill("1000")
                expect(page.locator(".mortgage-result-card")).to_have_count(4)
                scenario_20_30 = page.locator(
                    '[data-mortgage-scenario="20-30"]'
                )
                expect(scenario_20_30).to_contain_text("800 萬")
                expect(scenario_20_30).to_contain_text("NT$ 30,784")
                expect(scenario_20_30).to_contain_text("308.2 萬")
                expect(scenario_20_30).to_contain_text("1,108.2 萬")

                page.set_viewport_size({"width": 600, "height": 900})
                first_box = page.locator(".mortgage-result-card").nth(0).bounding_box()
                second_box = page.locator(".mortgage-result-card").nth(1).bounding_box()
                assert first_box is not None and second_box is not None
                assert round(first_box["x"]) == round(second_box["x"])
                assert second_box["y"] > first_box["y"]
                page.set_viewport_size({"width": 1440, "height": 1000})

                page.locator("#mortgage-rate").fill("0")
                expect(scenario_20_30).to_contain_text("NT$ 22,222")
                expect(scenario_20_30).to_contain_text("0 萬")
                page.locator("#mortgage-rate").fill("")
                expect(page.locator("#mortgage-error")).to_have_text(
                    "年利率請輸入 0%～20%。"
                )
                page.locator("#mortgage-rate").fill("0")
                page.locator("#mortgage-price").fill("-1")
                expect(page.locator("#mortgage-error")).to_have_text(
                    "請輸入大於 0 的房屋總價。"
                )
                expect(page.locator(".mortgage-result-card")).to_have_count(0)
                page.locator("#mortgage-close").click()
                expect(mortgage_dialog).not_to_be_visible()
                age_sort = page.locator('[data-sort-field="age"]')
                age_sort.click()
                expect(age_sort).to_have_attribute("aria-label", "屋齡新到舊")
                expect(age_sort).to_contain_text("↑")
                age_sort.click()
                expect(age_sort).to_have_attribute("aria-label", "屋齡舊到新")
                expect(age_sort).to_contain_text("↓")

                expect(page.locator("#active-goal-title")).to_have_text("大樓・華廈")
                expect(page.locator("#updated-at")).to_contain_text("耗時 2 分 5 秒")

                acceptable = page.locator('.tab[data-status="acceptable"]')
                expect(acceptable).to_have_class(re.compile(r"\bactive\b"))
                expect(page.locator("#results")).to_contain_text(
                    "E2E 可接受大樓"
                )
                district_tags = page.locator("#result-district-tags")
                expect(district_tags.locator("button")).to_have_count(7)
                district_tags.get_by_role("button", name="楠梓區", exact=True).click()
                expect(
                    district_tags.get_by_role("button", name="楠梓區", exact=True)
                ).to_have_attribute("aria-pressed", "true")

                acceptable_card = page.locator(
                    ".listing-card", has_text="E2E 可接受大樓"
                )
                mortgage_quick_link = acceptable_card.locator(
                    ".district-tools > .mortgage-card-button"
                )
                quick_link_box = mortgage_quick_link.bounding_box()
                assert quick_link_box is not None
                assert quick_link_box["width"] < 100
                assert quick_link_box["height"] < 32
                mortgage_quick_link.click()
                expect(mortgage_dialog).to_be_visible()
                expect(page.locator("#mortgage-price")).to_have_value("1150")
                expect(page.locator("#mortgage-rate")).to_have_value("0")
                page.locator("#mortgage-close").click()

                favorite_button = acceptable_card.locator(".favorite-toggle")
                favorite_box_before = favorite_button.bounding_box()
                favorite_button.click()
                acceptable_card = page.locator(
                    ".listing-card", has_text="E2E 可接受大樓"
                )
                favorite_button = acceptable_card.locator(".favorite-toggle")
                expect(favorite_button).to_contain_text("已收藏")
                favorite_box_after = favorite_button.bounding_box()
                assert favorite_box_before is not None and favorite_box_after is not None
                assert abs(favorite_box_before["width"] - favorite_box_after["width"]) < 1
                assert abs(favorite_box_before["height"] - favorite_box_after["height"]) < 1

                page.locator('.tab[data-status="favorites"]').click()
                favorite_filters = page.locator("#favorite-status-filters")
                expect(favorite_filters).to_be_visible()
                expect(favorite_filters.locator("button")).to_have_count(5)
                favorite_filters.get_by_role("button", name=re.compile("待查核")).click()
                expect(page.locator("#results")).to_contain_text("E2E 可接受大樓")
                page.locator(".favorite-note summary").click()
                note = page.locator(".favorite-note textarea")
                note.fill("地點很好，屋況需要整理")
                page.locator(".favorite-note-save").click()
                expect(page.locator("#status-message")).to_have_text("收藏備註已儲存")
                expect(page.locator(".favorite-note textarea")).to_have_value(
                    "地點很好，屋況需要整理"
                )
                page.locator(".real-price-open").click()
                workspace = page.locator("#favorite-workspace")
                expect(workspace).to_be_visible()
                expect(workspace.locator(".real-price-summary")).to_be_visible()
                expect(workspace.locator(".closest-match.best")).to_contain_text("可能同一棟 91%")
                expect(workspace.locator(".real-price-table-wrap tbody tr")).to_have_count(1)
                expect(workspace.locator(".real-price-period button")).to_have_count(4)
                workspace.locator(".workspace-close").click()
                page.locator("#favorite-map-button").click()
                workspace = page.locator("#favorite-workspace")
                expect(workspace).to_be_visible()
                expect(workspace).to_contain_text("收藏地圖與通勤")
                expect(workspace).to_contain_text("公司・義大醫院")
                expect(workspace).to_contain_text("住家")
                expect(workspace.locator(".commute-destination a")).to_have_count(4)
                workspace.locator(".workspace-close").click()
                acceptable.click()

                page.locator("#current-results-search").fill("E2E-NEAR")
                expect(page.locator("#visible-result-count")).to_have_text(
                    "搜尋全部分類：找到 1 組"
                )
                expect(page.locator("#results")).to_contain_text(
                    "E2E 跨分類搜尋房源"
                )
                page.locator("#clear-results-search").click()
                expect(page.locator("#results")).to_contain_text(
                    "E2E 可接受大樓"
                )

                near_match = page.locator('.tab[data-status="near_match"]')
                near_match.click()
                failure_filters = page.locator("#near-failure-filter-buttons")
                expect(failure_filters).to_contain_text("無車位 1")
                expect(failure_filters).to_contain_text("非平面車位 1")
                failure_sort = page.locator('[data-sort-field="failures"]')
                expect(failure_sort).to_have_attribute(
                    "aria-label", "不符合項目少到多"
                )
                expect(failure_sort).to_contain_text("↑")
                failure_sort.click()
                expect(failure_sort).to_have_attribute(
                    "aria-label", "不符合項目多到少"
                )
                expect(failure_sort).to_contain_text("↓")

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
                expect(page.locator(".listing-import-panel")).to_be_hidden()
                expect(pending).to_have_class(re.compile(r"\bactive\b"))
                expect(page.locator("#results")).to_contain_text(
                    "E2E 待確認預售"
                )
                expect(
                    page.locator(".listing-card", has_text="E2E 待確認預售")
                    .locator(".mortgage-card-button")
                ).to_be_disabled()

                page.locator("#selected-settings-button").click()
                dialog = page.locator("#settings-dialog")
                expect(dialog).to_be_visible()
                expect(dialog).to_contain_text("調整目標 03條件")
                page.locator("#settings-close").click()
                expect(dialog).not_to_be_visible()

                assert browser_problems == []
                page.route(
                    "**/api/results",
                    lambda route: route.fulfill(
                        status=500,
                        content_type="text/html",
                        body="<!doctype html><title>stale server</title>",
                    ),
                )
                page.reload(wait_until="networkidle")
                expect(page.locator("#results")).to_contain_text(
                    "本機服務版本可能已更新"
                )

                browser.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
