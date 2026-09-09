from __future__ import annotations

import time
from typing import Any, Callable

from . import web_app_v16 as previous
from . import web_app_v7 as crawl_app
from .crawler_leju_presale import BrowserLejuPresaleCrawler, SOURCE_NAME
from .user_models import HomeListing


app = previous.app
base = previous.base
_index_v16 = previous.index_v16
_crawl_before_leju: Callable[..., tuple[list[HomeListing], dict[str, Any]]] | None = None


def _crawl_with_leju(
    profile: str, settings: dict, source: dict, mode: str
) -> tuple[list[HomeListing], dict[str, Any]]:
    if _crawl_before_leju is None:
        raise RuntimeError("預售屋來源尚未初始化")
    if profile != "預售屋" or not source.get("leju_enabled", True):
        return _crawl_before_leju(profile, settings, source, mode)

    started = time.time()
    fetched: list[HomeListing] = []
    source_diagnostics: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    try:
        listings_591, diagnostics_591 = _crawl_before_leju(
            profile, settings, source, mode
        )
        fetched.extend(listings_591)
        source_diagnostics["591預售屋"] = diagnostics_591
    except Exception as exc:
        errors.append(f"591預售屋：{type(exc).__name__}: {exc}")
        source_diagnostics["591預售屋"] = {
            "source": "591預售屋", "error": str(exc),
            "error_type": type(exc).__name__,
        }

    try:
        crawler = BrowserLejuPresaleCrawler(
            districts=settings["districts"],
            max_projects=int(source.get("leju_max_projects", 80)),
            delay_seconds=max(2.0, float(source.get("delay_seconds", 2))),
            headless=False,
            background=True,
        )
        listings_leju = crawler.fetch()
        fetched.extend(listings_leju)
        source_diagnostics[SOURCE_NAME] = crawler.stats
    except Exception as exc:
        errors.append(f"{SOURCE_NAME}：{type(exc).__name__}: {exc}")
        source_diagnostics[SOURCE_NAME] = {
            "source": SOURCE_NAME, "error": str(exc),
            "error_type": type(exc).__name__,
        }

    if not fetched and errors:
        raise RuntimeError("；".join(errors))
    return fetched, {
        "profile": profile,
        "mode": mode,
        "district_count": len(settings["districts"]),
        "districts": settings["districts"],
        "pages_requested": None,
        "publish_days": 0,
        "details_limit": int(settings["search"]["presale_details"]),
        "fetched": len(fetched),
        "detail_failures": 0,
        "cache_expired": False,
        "duration_seconds": round(time.time() - started, 1),
        "sources": source_diagnostics,
        "partial_errors": errors,
    }


def index_v17():
    html = _index_v16()
    assets = (
        '<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" '
        'integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin="">'
        '<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" '
        'integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" '
        'crossorigin="" defer></script>'
        '<link rel="stylesheet" href="/static/dashboard_v17.css">'
        '<script src="/static/dashboard_v17.js" defer></script>'
    )
    return html.replace("</head>", assets + "</head>")


def activate() -> None:
    global _crawl_before_leju
    previous.activate()
    if crawl_app._crawl_for_mode is not _crawl_with_leju:
        _crawl_before_leju = crawl_app._crawl_for_mode
        crawl_app._crawl_for_mode = _crawl_with_leju
    app.view_functions["index"] = index_v17


def main() -> None:
    activate()
    base.main()


if __name__ == "__main__":
    main()
