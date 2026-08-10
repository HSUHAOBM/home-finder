from __future__ import annotations

import re
from contextlib import ExitStack
from dataclasses import dataclass
from typing import Any, Callable

from playwright.sync_api import sync_playwright


REMOVED_MARKERS = (
    "此物件已下架",
    "此房屋已下架",
    "物件已下架",
    "房屋已下架",
    "物件不存在",
    "房屋不存在",
    "找不到此物件",
    "找不到此房屋",
    "案件已關閉",
    "本物件已停售",
)
BLOCKED_MARKERS = (
    "cloudflare",
    "access denied",
    "attention required",
    "verify you are human",
    "請完成安全驗證",
    "存取遭拒",
)


@dataclass(frozen=True)
class AvailabilityResult:
    status: str
    reason: str


def classify_availability(
    *, http_status: int | None, body: str, final_url: str
) -> AvailabilityResult:
    compact = re.sub(r"\s+", " ", body or "").strip()
    lowered = compact.lower()
    if http_status in {404, 410}:
        return AvailabilityResult("removed", f"網址回傳 HTTP {http_status}")
    if http_status in {403, 429} or any(marker in lowered for marker in BLOCKED_MARKERS):
        return AvailabilityResult("unknown", "網站阻擋或要求驗證")
    if http_status is not None and http_status >= 500:
        return AvailabilityResult("unknown", f"網站暫時錯誤（HTTP {http_status}）")
    marker = next((marker for marker in REMOVED_MARKERS if marker in compact), None)
    if marker:
        return AvailabilityResult("removed", f"頁面顯示「{marker}」")
    if http_status is not None and 200 <= http_status < 400 and compact:
        return AvailabilityResult("available", "網址目前可正常開啟")
    return AvailabilityResult("unknown", f"無法確認網址狀態：{final_url}")


class FavoriteAvailabilityChecker:
    def __init__(self, *, headless: bool = True, timeout_ms: int = 20_000):
        self.headless = headless
        self.timeout_ms = timeout_ms

    def check_many(
        self,
        favorites: list[dict[str, Any]],
        *,
        on_result: Callable[[dict[str, Any], AvailabilityResult], None],
    ) -> None:
        if not favorites:
            return
        with sync_playwright() as playwright, ExitStack() as cleanup:
            browser = playwright.chromium.launch(headless=self.headless)
            cleanup.callback(lambda: browser.is_connected() and browser.close())
            page = browser.new_page(locale="zh-TW")
            for favorite in favorites:
                url = str(favorite.get("url") or "").strip()
                if not url:
                    on_result(favorite, AvailabilityResult("unknown", "收藏沒有網址"))
                    continue
                try:
                    response = page.goto(
                        url, wait_until="domcontentloaded", timeout=self.timeout_ms
                    )
                    page.locator("body").wait_for(timeout=min(self.timeout_ms, 15_000))
                    body = page.locator("body").inner_text(timeout=10_000)
                    result = classify_availability(
                        http_status=response.status if response else None,
                        body=body,
                        final_url=page.url,
                    )
                except Exception as exc:
                    result = AvailabilityResult(
                        "unknown", f"查核失敗：{type(exc).__name__}"
                    )
                on_result(favorite, result)
