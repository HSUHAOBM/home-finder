from __future__ import annotations

import copy
import time
from typing import Any

from . import web_app_v7 as crawl_app
from . import web_app_v8 as favorites_app
from . import web_app_v11 as previous
from .favorite_availability import AvailabilityResult, FavoriteAvailabilityChecker


app = previous.app
base = previous.base
_index_v11 = previous.index_v11
_latest_fetched_keys: dict[str, set[str]] = {}


def _key(item: dict[str, Any] | Any) -> str:
    source = item.get("source") if isinstance(item, dict) else item.source
    external_id = item.get("id") if isinstance(item, dict) else item.external_id
    return favorites_app._favorite_key(source, external_id)


def audit_favorite_availability(
    fetched_keys: set[str],
    *,
    profile: str | None = None,
    checker: FavoriteAvailabilityChecker | None = None,
    checked_at: str | None = None,
) -> dict[str, int]:
    checked_at = checked_at or base._iso_now()
    checker = checker or FavoriteAvailabilityChecker(headless=True)
    with favorites_app._favorites_lock:
        items = favorites_app._load_favorite_items()
        refreshed = copy.deepcopy(items)

    counts = {
        "available": 0,
        "removed": 0,
        "unknown": 0,
        "current": 0,
        "url_checks": 0,
    }
    pending: list[dict[str, Any]] = []
    audit_updates: dict[str, dict[str, str]] = {}

    def apply_result(item: dict[str, Any], result: AvailabilityResult) -> None:
        previous_status = item.get("availability_status")
        history = item.get("availability_history", [])
        if not isinstance(history, list):
            history = []
        if previous_status != result.status:
            history.append({
                "checked_at": checked_at,
                "from": previous_status,
                "to": result.status,
                "reason": result.reason,
            })
            history = history[-30:]
        update = {
            "availability_status": result.status,
            "availability_checked_at": checked_at,
            "availability_reason": result.reason,
            "availability_history": history,
        }
        if result.status == "removed":
            update["removed_at"] = item.get("removed_at") or checked_at
        item.update(update)
        audit_updates[_key(item)] = update
        counts[result.status] += 1

    for item in refreshed:
        if profile and item.get("profile") != profile:
            continue
        if _key(item) in fetched_keys:
            counts["current"] += 1
            apply_result(item, AvailabilityResult("available", "本次爬蟲已找到"))
        else:
            pending.append(item)

    counts["url_checks"] = len(pending)
    checker.check_many(pending, on_result=apply_result)
    with favorites_app._favorites_lock:
        current_items = favorites_app._load_favorite_items()
        for item in current_items:
            update = audit_updates.get(_key(item))
            if update:
                item.update(update)
        favorites_app._write_favorite_items(current_items)
    return counts


def index_v12():
    html = _index_v11()
    assets = (
        '<link rel="stylesheet" href="/static/dashboard_v12.css">'
        '<script src="/static/dashboard_v12.js" defer></script>'
    )
    return html.replace("</head>", assets + "</head>")


def activate() -> None:
    previous.activate()
    original_crawl_for_mode = crawl_app._crawl_for_mode
    original_record_successful_crawl = crawl_app._record_successful_crawl

    def crawl_for_mode_v12(profile, settings, source, mode):
        listings, diagnostics = original_crawl_for_mode(profile, settings, source, mode)
        _latest_fetched_keys[profile] = {_key(item) for item in listings}
        return listings, diagnostics

    def record_successful_crawl_v12(profile, mode, diagnostics):
        audit_started = time.monotonic()
        base._update_state(
            phase="checking_favorites",
            message=f"{profile}爬蟲完成，正在查核本次未出現的收藏網址",
        )
        try:
            diagnostics["favorite_availability"] = audit_favorite_availability(
                _latest_fetched_keys.pop(profile, set()), profile=profile
            )
        except Exception as exc:
            app.logger.exception("Favorite availability audit failed")
            diagnostics["favorite_availability"] = {
                "error": type(exc).__name__,
                "message": str(exc),
            }
        diagnostics["favorite_availability"]["duration_seconds"] = round(
            time.monotonic() - audit_started, 1
        )
        all_diagnostics = crawl_app._load_json(crawl_app.DIAGNOSTICS_PATH)
        all_diagnostics[profile] = diagnostics
        crawl_app._write_json(crawl_app.DIAGNOSTICS_PATH, all_diagnostics)
        return original_record_successful_crawl(profile, mode, diagnostics)

    crawl_app._crawl_for_mode = crawl_for_mode_v12
    crawl_app._record_successful_crawl = record_successful_crawl_v12
    app.view_functions["index"] = index_v12


def main() -> None:
    activate()
    base.main()


if __name__ == "__main__":
    main()
