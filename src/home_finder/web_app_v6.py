from __future__ import annotations

import copy
import json
import math
import re
import threading
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from flask import jsonify, render_template, request

from . import web_app as base
from . import web_app_v5 as previous
from .listing_history import annotate_history
from .listing_identity import source_listing_ref
from .make_report import render_report
from .result_store import read_result_records, write_result_records
from .storage import atomic_write_text
from .user_models import HomeListing
from .user_ranking_v6 import evaluate_all


PROFILES = previous.PROFILES
SEARCH_MODES = ("daily", "full")


def load_settings() -> dict:
    return previous.load_settings()


def _normal(value: Any) -> str:
    return re.sub(r"[\s\-－—・,，。()（）]+", "", str(value or "")).lower()


def _physical_key(record: dict[str, Any]) -> tuple[Any, ...]:
    listing = record["listing"]
    profile = record.get("profile")
    community = _normal(listing.get("community"))
    address = _normal(listing.get("address"))
    duplicate_ids = [str(item) for item in record.get("duplicate_ids", [])]
    if duplicate_ids:
        own_ref = source_listing_ref(listing.get("source"), listing.get("external_id"))
        group_id = min([own_ref] + duplicate_ids)
        return ("duplicate", profile, group_id)

    if community and address:
        return (
            "property",
            profile,
            listing.get("district"),
            community,
            address,
            listing.get("current_floor"),
            listing.get("total_floors"),
            round(float(listing.get("main_area_ping") or 0), 1),
        )
    return (
        "listing",
        profile,
        listing.get("source"),
        str(listing.get("external_id")),
    )


def cluster_selected_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected = base.select_listing_results(records)
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for record in selected:
        grouped.setdefault(_physical_key(record), []).append(record)

    status_order = {"qualified": 0, "needs_verification": 1, "rejected": 2}
    clustered: list[dict[str, Any]] = []
    for candidates in grouped.values():
        best = min(
            candidates,
            key=lambda item: (
                status_order.get(item.get("status", "rejected"), 9),
                -float(item.get("score", 0)),
            ),
        )
        item = copy.deepcopy(best)
        item["_source_variants"] = [
            {
                "id": candidate["listing"].get("external_id"),
                "source": candidate["listing"].get("source"),
                "origin_source": candidate["listing"].get("origin_source"),
                "title": candidate["listing"].get("title"),
                "url": candidate["listing"].get("url"),
                "price": candidate["listing"].get("total_price_wan"),
            }
            for candidate in sorted(
                candidates,
                key=lambda candidate: float(
                    candidate["listing"].get("total_price_wan") or 999999
                ),
            )
        ]
        clustered.append(item)

    return sorted(
        clustered,
        key=lambda item: (
            status_order.get(item.get("status", "rejected"), 9),
            -float(item.get("score", 0)),
            float(item["listing"].get("total_price_wan") or 999999),
        ),
    )


def _ideal_gaps(record: dict[str, Any], settings: dict) -> list[str]:
    listing = record["listing"]
    profile = record["profile"]
    config = settings["profiles"][profile]
    gaps: list[str] = []

    price = listing.get("total_price_wan")
    target_price = float(config["target_price"])
    if price is None or float(price) <= 0:
        gaps.append("理想總價尚未確認")
    elif float(price) > target_price:
        gaps.append(f"總價高於理想目標 {target_price:g} 萬")

    preferred_baths = config.get("preferred_min_baths")
    if preferred_baths is not None:
        baths = listing.get("baths")
        if baths is None:
            gaps.append("衛浴數尚未確認")
        elif float(baths) < float(preferred_baths):
            gaps.append(f"未達 {float(preferred_baths):g} 衛浴偏好")

    preferred_age = config.get("preferred_max_age")
    if preferred_age is not None and profile != "預售屋":
        age = listing.get("age_years")
        if age is None:
            gaps.append("屋齡尚未確認")
        elif float(age) > float(preferred_age):
            gaps.append(f"屋齡超過偏好 {float(preferred_age):g} 年")

    if profile == "大樓公寓華廈" and config.get("prefer_high_floor"):
        current = listing.get("current_floor")
        total = listing.get("total_floors")
        ratio = float(config.get("min_floor_ratio", 2 / 3))
        if current is None or not total:
            gaps.append("樓層比例尚未確認")
        else:
            minimum = math.ceil(float(total) * ratio - 1e-9)
            if int(current) < minimum:
                gaps.append(f"樓層未達全棟 2/3（需 {minimum} 樓以上）")

    if profile == "透天別墅" and config.get("prefer_garden"):
        if not listing.get("has_garden"):
            gaps.append("未確認有花園或庭院")
    return gaps


def _card(record: dict[str, Any], status: str, ideal_gaps: list[str] | None = None) -> dict[str, Any]:
    card = base._card(record)
    card["status"] = status
    card["ideal_gaps"] = ideal_gaps or []
    card["variants"] = record.get("_source_variants", [])
    return card


def build_dashboard_payload(records: list[dict[str, Any]]) -> dict[str, Any]:
    settings = load_settings()
    clustered = cluster_selected_records(records)
    groups: dict[str, list[dict[str, Any]]] = {
        "exact_match": [],
        "acceptable": [],
        "qualified": [],
        "needs_verification": [],
        "near_match": [],
        "rejected": [],
    }
    insights: dict[str, dict[str, Any]] = {}

    for profile in PROFILES:
        profile_records = [item for item in clustered if item.get("profile") == profile]
        failure_counts: Counter[str] = Counter()
        for record in profile_records:
            status = record.get("status")
            if status == "qualified":
                gaps = _ideal_gaps(record, settings)
                category = "acceptable" if gaps else "exact_match"
                card = _card(record, category, gaps)
                groups[category].append(card)
                groups["qualified"].append(card)
            elif status == "needs_verification":
                groups["needs_verification"].append(
                    _card(record, "needs_verification")
                )
            else:
                failures = record.get("hard_failures", [])
                failure_counts.update(failures)
                if 1 <= len(failures) <= 2:
                    groups["near_match"].append(_card(record, "near_match"))
                else:
                    groups["rejected"].append(_card(record, "rejected"))

        insights[profile] = {
            "exact_match": len(
                [item for item in groups["exact_match"] if item["profile"] == profile]
            ),
            "acceptable": len(
                [item for item in groups["acceptable"] if item["profile"] == profile]
            ),
            "needs_verification": len(
                [
                    item
                    for item in groups["needs_verification"]
                    if item["profile"] == profile
                ]
            ),
            "near_match": len(
                [item for item in groups["near_match"] if item["profile"] == profile]
            ),
            "rejected": len(
                [item for item in groups["rejected"] if item["profile"] == profile]
            ),
            "source_listings": sum(
                len(item.get("_source_variants", [])) for item in profile_records
            ),
            "properties": len(profile_records),
            "top_reasons": [
                {"reason": reason, "count": count}
                for reason, count in failure_counts.most_common(3)
            ],
        }

    updated_at = None
    if base.RESULTS_PATH.exists():
        updated_at = datetime.fromtimestamp(
            base.RESULTS_PATH.stat().st_mtime, tz=timezone.utc
        ).isoformat()
    exact_count = len(groups["exact_match"])
    acceptable_count = len(groups["acceptable"])
    return {
        "updated_at": updated_at,
        "summary": {
            "total": len(clustered),
            "source_listings": sum(
                len(item.get("_source_variants", [])) for item in clustered
            ),
            "exact_match": exact_count,
            "acceptable": acceptable_count,
            "qualified": exact_count + acceptable_count,
            "needs_verification": len(groups["needs_verification"]),
            "near_match": len(groups["near_match"]),
            "rejected": len(groups["rejected"]),
        },
        "groups": groups,
        "profile_insights": insights,
    }


def load_dashboard_payload() -> dict[str, Any]:
    if not base.RESULTS_PATH.exists():
        return build_dashboard_payload([])
    return build_dashboard_payload(read_result_records(base.RESULTS_PATH))


def merge_search_results(
    existing: list[HomeListing],
    fetched: list[HomeListing],
    profile: str,
    mode: str,
) -> list[HomeListing]:
    if mode == "full":
        return previous.merge_target_listings(existing, fetched, profile)
    merged: dict[tuple[str, str], HomeListing] = {
        (item.source, item.external_id): item for item in existing
    }
    for item in fetched:
        item.search_profile = profile
        merged[(item.source, item.external_id)] = item
    return list(merged.values())


def _crawl_for_mode(
    profile: str, settings: dict, source: dict, mode: str
) -> list[HomeListing]:
    crawl_settings = copy.deepcopy(settings)
    if mode == "full":
        crawl_settings["search"]["pages"] = 10
        crawl_settings["search"]["publish_days"] = 30
    return previous._crawl_profile(profile, crawl_settings, source)


def _write_results(records: list[dict[str, Any]]) -> None:
    write_result_records(base.RESULTS_PATH, records)
    atomic_write_text(
        base.SUMMARY_PATH, render_report(cluster_selected_records(records))
    )


def re_evaluate_existing(settings: dict) -> None:
    listings = previous._load_existing_listings()
    if not listings:
        return
    _write_results([item.to_dict() for item in evaluate_all(listings, settings)])


def _run_search(profile: str, mode: str) -> None:
    try:
        settings = load_settings()
        config = json.loads(base.CONFIG_PATH.read_text(encoding="utf-8"))
        mode_label = "完整盤點（30 天／10 頁）" if mode == "full" else "每日更新"
        base._update_state(
            phase="crawling",
            active_profile=profile,
            search_mode=mode,
            message=f"正在執行「{profile}」{mode_label}…",
        )
        fetched = _crawl_for_mode(profile, settings, config["source"], mode)
        fetched = annotate_history(
            fetched, path=base.BASE_DIR / "data" / "listing_history.json"
        )
        if profile == "預售屋" and mode == "daily":
            fetched = previous._filter_recent_presales(
                fetched, settings["search"]["publish_days"]
            )

        listings = merge_search_results(
            previous._load_existing_listings(), fetched, profile, mode
        )
        base._update_state(
            phase="ranking", message="正在合併重複刊登並計算完全符合程度…"
        )
        records = [item.to_dict() for item in evaluate_all(listings, settings)]
        _write_results(records)
        insight = build_dashboard_payload(records)["profile_insights"][profile]
        base._update_state(
            running=False,
            phase="complete",
            active_profile=profile,
            search_mode=mode,
            message=(
                f"{profile}{mode_label}完成：{insight['exact_match']} 組完全符合、"
                f"{insight['acceptable']} 組可接受、"
                f"{insight['needs_verification']} 組待確認"
            ),
            finished_at=base._iso_now(),
            error=None,
        )
    except Exception as exc:  # pragma: no cover - live website behavior
        base._update_state(
            running=False,
            phase="error",
            active_profile=profile,
            search_mode=mode,
            message=f"{profile}搜尋未完成，原有結果已保留",
            finished_at=base._iso_now(),
            error=str(exc),
        )


app = base.app


def index_v6():
    html = render_template("dashboard_v3.html")
    html = html.replace(
        "</head>",
        '<link rel="icon" href="data:,">'
        '<link rel="stylesheet" href="/static/dashboard_v4.css">'
        '<link rel="stylesheet" href="/static/dashboard_v5.css">'
        '<link rel="stylesheet" href="/static/dashboard_v6.css">'
        '<script src="/static/dashboard_v4.js" defer></script>'
        '<script src="/static/dashboard_v5.js" defer></script>'
        '<script src="/static/dashboard_v6.js" defer></script></head>',
    )
    return html


def api_results_v6():
    try:
        return jsonify(load_dashboard_payload())
    except (OSError, json.JSONDecodeError) as exc:
        return jsonify({"error": f"無法讀取現有結果：{exc}"}), 500


def api_settings_post_v6():
    if base._state_snapshot()["running"]:
        return jsonify({"error": "搜尋進行中，完成後才能調整條件"}), 409
    try:
        settings = previous.validate_settings(request.get_json(silent=True) or {})
        previous.save_settings(settings)
        re_evaluate_existing(settings)
        return jsonify({"settings": settings, "results": load_dashboard_payload()})
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        return jsonify({"error": str(exc)}), 400


def api_search_v6():
    payload = request.get_json(silent=True) or {}
    profile = payload.get("profile")
    mode = payload.get("mode", "daily")
    if profile not in PROFILES:
        return jsonify({"error": "請先選擇要搜尋的目標"}), 400
    if mode not in SEARCH_MODES:
        return jsonify({"error": "搜尋模式只能選每日更新或完整盤點"}), 400
    with base._state_lock:
        if base._state["running"]:
            return jsonify(dict(base._state)), 409
        base._state.update(
            running=True,
            phase="starting",
            active_profile=profile,
            search_mode=mode,
            message=f"準備搜尋「{profile}」…",
            started_at=base._iso_now(),
            finished_at=None,
            error=None,
        )
        snapshot = dict(base._state)
    threading.Thread(target=_run_search, args=(profile, mode), daemon=True).start()
    return jsonify(snapshot), 202


app.view_functions["index"] = index_v6
app.view_functions["api_results"] = api_results_v6
app.view_functions["api_settings_post"] = api_settings_post_v6
app.view_functions["api_search"] = api_search_v6
base.load_dashboard_payload = load_dashboard_payload


def main() -> None:
    base.main()


if __name__ == "__main__":
    main()
