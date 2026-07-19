from __future__ import annotations

import copy
import json
import threading
from collections import Counter
from typing import Any

from flask import jsonify, render_template, request

from . import web_app as base
from . import web_app_v4 as previous
from .crawler_591_multi import MultiPage591ResaleCrawler
from .crawler_591_presale_multi import MultiDistrict591PresaleCrawler
from .listing_history import annotate_history
from .make_report import render_report
from .user_models import HomeListing
from .user_ranking_v6 import evaluate_all


PROFILES = ("大樓公寓華廈", "透天別墅", "預售屋")
DEFAULT_SETTINGS = copy.deepcopy(previous.DEFAULT_SETTINGS)
DEFAULT_SETTINGS["profiles"]["大樓公寓華廈"]["require_high_floor"] = False


def load_settings() -> dict:
    settings = previous.load_settings()
    config = json.loads(base.CONFIG_PATH.read_text(encoding="utf-8"))
    stored_condo = (
        config.get("editable_criteria", {})
        .get("profiles", {})
        .get("大樓公寓華廈", {})
    )
    if "require_high_floor" not in stored_condo:
        settings["profiles"]["大樓公寓華廈"]["require_high_floor"] = False
    settings["profiles"]["大樓公寓華廈"].setdefault("min_floor_ratio", 2 / 3)
    return settings


def validate_settings(raw: dict) -> dict:
    return previous.validate_settings(raw)


def save_settings(settings: dict) -> None:
    previous.save_settings(settings)


def _listing_profile(listing: HomeListing) -> str:
    if listing.search_profile in PROFILES:
        return str(listing.search_profile)
    if listing.deal_kind == "預售屋":
        return "預售屋"
    if listing.property_type and ("透天" in listing.property_type or "別墅" in listing.property_type):
        return "透天別墅"
    return "大樓公寓華廈"


def _unique_listings(records: list[dict[str, Any]]) -> list[HomeListing]:
    listings: dict[tuple[str, str], HomeListing] = {}
    for record in records:
        data = record.get("listing", {})
        external_id = str(data.get("external_id", ""))
        if not external_id:
            continue
        key = (str(data.get("source", "")), external_id)
        if key not in listings:
            listings[key] = HomeListing.from_dict(data)
    return list(listings.values())


def _load_existing_listings() -> list[HomeListing]:
    if not base.RESULTS_PATH.exists():
        return []
    return _unique_listings(json.loads(base.RESULTS_PATH.read_text(encoding="utf-8")))


def merge_target_listings(
    existing: list[HomeListing], new_listings: list[HomeListing], profile: str
) -> list[HomeListing]:
    """Replace only one goal's source set and keep the other two goals intact."""
    merged: dict[tuple[str, str], HomeListing] = {}
    for listing in existing:
        if _listing_profile(listing) != profile:
            merged[(listing.source, listing.external_id)] = listing
    for listing in new_listings:
        listing.search_profile = profile
        merged[(listing.source, listing.external_id)] = listing
    return list(merged.values())


def re_evaluate_existing(settings: dict) -> None:
    if not base.RESULTS_PATH.exists():
        return
    listings = _load_existing_listings()
    records = [item.to_dict() for item in evaluate_all(listings, settings)]
    _write_results(records)


def _write_results(records: list[dict[str, Any]]) -> None:
    base.RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    base.RESULTS_PATH.write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    selected = base.select_listing_results(records)
    base.SUMMARY_PATH.write_text(render_report(selected), encoding="utf-8")


def _crawl_profile(profile: str, settings: dict, source: dict) -> list[HomeListing]:
    search = settings["search"]
    delay = max(2.0, float(source.get("delay_seconds", 2)))
    # Searches must never open a Playwright window. The dashboard is opened only once.
    if profile == "預售屋":
        return MultiDistrict591PresaleCrawler(
            districts=settings["districts"],
            max_details=search["presale_details"],
            delay_seconds=delay,
            headless=True,
        ).fetch()
    return MultiPage591ResaleCrawler(
        profile=profile,
        districts=settings["districts"],
        max_pages=search["pages"],
        publish_days=search["publish_days"],
        max_details=search["resale_details"],
        delay_seconds=delay,
        headless=True,
    ).fetch()


def _run_search(profile: str) -> None:
    try:
        settings = load_settings()
        config = json.loads(base.CONFIG_PATH.read_text(encoding="utf-8"))
        search = settings["search"]
        if profile == "預售屋":
            message = "目標 03：正在讀取四個行政區的預售屋…"
        else:
            label = "大樓／華廈" if profile == "大樓公寓華廈" else "透天／車墅"
            message = f"正在搜尋{label}：近 {search['publish_days'] or '不限'} 天，共 {search['pages']} 頁…"
        base._update_state(phase="crawling", active_profile=profile, message=message)

        fetched = _crawl_profile(profile, settings, config["source"])
        base._update_state(phase="history", message="正在更新新房源與曾看過紀錄…")
        fetched = annotate_history(
            fetched,
            path=base.BASE_DIR / "data" / "listing_history.json",
        )
        if profile == "預售屋":
            fetched = previous._filter_recent_presales(fetched, search["publish_days"])

        listings = merge_target_listings(_load_existing_listings(), fetched, profile)
        base._update_state(phase="ranking", message=f"正在套用「{profile}」條件並整理差一項候選…")
        records = [item.to_dict() for item in evaluate_all(listings, settings)]
        _write_results(records)

        payload = build_dashboard_payload(records)
        insight = payload["profile_insights"][profile]
        note = "；來源本次沒有讀到房源" if not fetched else ""
        base._update_state(
            running=False,
            phase="complete",
            active_profile=profile,
            message=(
                f"{profile}完成：{insight['qualified']} 筆符合、"
                f"{insight['needs_verification']} 筆待確認、"
                f"{insight['near_match']} 筆只差一項{note}"
            ),
            finished_at=base._iso_now(),
            error=None,
        )
    except Exception as exc:  # pragma: no cover - depends on live website
        base._update_state(
            running=False,
            phase="error",
            active_profile=profile,
            message=f"{profile}搜尋未完成，原有結果已保留",
            finished_at=base._iso_now(),
            error=str(exc),
        )


_original_preferred_profile = base._preferred_profile


def _preferred_profile_v5(listing: dict[str, Any]) -> str:
    profile = listing.get("search_profile")
    if profile in PROFILES:
        return profile
    return _original_preferred_profile(listing)


base._preferred_profile = _preferred_profile_v5


def build_dashboard_payload(records: list[dict[str, Any]]) -> dict[str, Any]:
    payload = base.build_dashboard_payload(records)
    selected = base.select_listing_results(records)
    near_matches: list[dict[str, Any]] = []
    insights: dict[str, dict[str, Any]] = {}
    for profile in PROFILES:
        profile_records = [item for item in selected if item.get("profile") == profile]
        failures: Counter[str] = Counter()
        near_count = 0
        for record in profile_records:
            if record.get("status") != "rejected":
                continue
            hard_failures = record.get("hard_failures", [])
            failures.update(hard_failures)
            if len(hard_failures) == 1:
                card = base._card(record)
                card["status"] = "near_match"
                near_matches.append(card)
                near_count += 1
        insights[profile] = {
            "qualified": sum(item.get("status") == "qualified" for item in profile_records),
            "needs_verification": sum(
                item.get("status") == "needs_verification" for item in profile_records
            ),
            "rejected": sum(item.get("status") == "rejected" for item in profile_records),
            "near_match": near_count,
            "top_reasons": [
                {"reason": reason, "count": count}
                for reason, count in failures.most_common(3)
            ],
        }
    payload["groups"]["near_match"] = sorted(
        near_matches,
        key=lambda item: (-float(item.get("score", 0)), float(item.get("price") or 999999)),
    )
    payload["profile_insights"] = insights
    return payload


def load_dashboard_payload() -> dict[str, Any]:
    if not base.RESULTS_PATH.exists():
        return build_dashboard_payload([])
    records = json.loads(base.RESULTS_PATH.read_text(encoding="utf-8"))
    return build_dashboard_payload(records)


app = base.app


def index_v5():
    html = render_template("dashboard_v3.html")
    html = html.replace(
        "</head>",
        '<link rel="stylesheet" href="/static/dashboard_v4.css">'
        '<link rel="stylesheet" href="/static/dashboard_v5.css">'
        '<script src="/static/dashboard_v4.js" defer></script>'
        '<script src="/static/dashboard_v5.js" defer></script></head>',
    )
    return html


def api_results_v5():
    try:
        return jsonify(load_dashboard_payload())
    except (OSError, json.JSONDecodeError) as exc:
        return jsonify({"error": f"無法讀取現有結果：{exc}"}), 500


def api_settings_get_v5():
    return jsonify(load_settings())


def api_settings_post_v5():
    if base._state_snapshot()["running"]:
        return jsonify({"error": "搜尋進行中，完成後才能調整條件"}), 409
    try:
        settings = validate_settings(request.get_json(silent=True) or {})
        save_settings(settings)
        re_evaluate_existing(settings)
        return jsonify({"settings": settings, "results": load_dashboard_payload()})
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        return jsonify({"error": str(exc)}), 400


def api_search_v5():
    payload = request.get_json(silent=True) or {}
    profile = payload.get("profile")
    if profile not in PROFILES:
        return jsonify({"error": "請先選擇要搜尋的大樓、透天或預售屋目標"}), 400
    with base._state_lock:
        if base._state["running"]:
            return jsonify(dict(base._state)), 409
        base._state.update(
            running=True,
            phase="starting",
            active_profile=profile,
            message=f"準備搜尋「{profile}」…",
            started_at=base._iso_now(),
            finished_at=None,
            error=None,
        )
        snapshot = dict(base._state)
    threading.Thread(target=_run_search, args=(profile,), daemon=True).start()
    return jsonify(snapshot), 202


app.view_functions["index"] = index_v5
app.view_functions["api_results"] = api_results_v5
app.view_functions["api_settings_get"] = api_settings_get_v5
app.view_functions["api_settings_post"] = api_settings_post_v5
app.view_functions["api_search"] = api_search_v5
base.load_dashboard_payload = load_dashboard_payload


def main() -> None:
    base.main()


if __name__ == "__main__":
    main()
