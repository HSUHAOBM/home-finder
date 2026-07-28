from __future__ import annotations

import time
from typing import Any

from . import web_app_v7 as crawl_app
from . import web_app_v8 as previous
from .crawler_yungching import BrowserYungchingCrawler, SOURCE_NAME
from .user_models import HomeListing


app = previous.app
base = previous.base
_original_crawl_for_mode = crawl_app._crawl_for_mode
_original_archive_skip_reason = crawl_app._full_scan_archive_skip_reason
_index_v8 = previous.index_v8


def _crawl_for_mode_multi(
    profile: str, settings: dict, source: dict, mode: str
) -> tuple[list[HomeListing], dict[str, Any]]:
    if profile == "預售屋" or not source.get("yungching_enabled", True):
        return _original_crawl_for_mode(profile, settings, source, mode)

    started = time.time()
    fetched: list[HomeListing] = []
    source_diagnostics: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    try:
        listings_591, diagnostics_591 = _original_crawl_for_mode(
            profile, settings, source, mode
        )
        fetched.extend(listings_591)
        source_diagnostics["591"] = diagnostics_591
    except Exception as exc:
        errors.append(f"591：{type(exc).__name__}: {exc}")
        source_diagnostics["591"] = {
            "source": "591",
            "error": str(exc),
            "error_type": type(exc).__name__,
        }

    search = settings["search"]
    max_pages = 5 if mode == "full" else min(int(search["pages"]), 3)
    max_details = int(
        source.get("yungching_max_details", min(int(search["resale_details"]), 20))
    )
    try:
        crawler = BrowserYungchingCrawler(
            profile=profile,
            districts=settings["districts"],
            max_pages=max_pages,
            max_details=max_details,
            max_price=float(settings["profiles"][profile]["max_price"]),
            delay_seconds=max(2.0, float(source.get("delay_seconds", 2))),
            headless=True,
        )
        listings_yungching = crawler.fetch()
        fetched.extend(listings_yungching)
        source_diagnostics[SOURCE_NAME] = crawler.stats
    except Exception as exc:
        errors.append(f"{SOURCE_NAME}：{type(exc).__name__}: {exc}")
        source_diagnostics[SOURCE_NAME] = {
            "source": SOURCE_NAME,
            "error": str(exc),
            "error_type": type(exc).__name__,
        }

    if not fetched and errors:
        raise RuntimeError("；".join(errors))

    diagnostics = {
        "profile": profile,
        "mode": mode,
        "district_count": len(settings["districts"]),
        "districts": settings["districts"],
        "pages_requested": search["pages"],
        "publish_days": search["publish_days"],
        "details_limit": int(search["resale_details"]) + max_details,
        "fetched": len(fetched),
        "detail_failures": sum(
            int(item.get("detail_failures") or 0)
            for item in source_diagnostics.values()
        ),
        "cache_expired": any(
            bool(item.get("cache_expired"))
            for item in source_diagnostics.values()
        ),
        "duration_seconds": round(time.time() - started, 1),
        "sources": source_diagnostics,
        "partial_errors": errors,
    }
    return fetched, diagnostics


def _full_scan_archive_skip_reason_multi(
    existing: list[HomeListing],
    fetched: list[HomeListing],
    profile: str,
    diagnostics: dict[str, Any],
) -> str | None:
    errors = diagnostics.get("partial_errors") or []
    if errors:
        return "部分來源失敗，避免誤判其他來源已下架"
    return _original_archive_skip_reason(existing, fetched, profile, diagnostics)


def index_v9():
    html = _index_v8()
    assets = (
        '<link rel="stylesheet" href="/static/dashboard_v9.css">'
        '<script src="/static/dashboard_v9.js" defer></script>'
    )
    return html.replace("</head>", assets + "</head>")


def activate() -> None:
    previous.activate()
    crawl_app._crawl_for_mode = _crawl_for_mode_multi
    crawl_app._full_scan_archive_skip_reason = _full_scan_archive_skip_reason_multi
    app.view_functions["index"] = index_v9


def main() -> None:
    activate()
    base.main()


if __name__ == "__main__":
    main()
