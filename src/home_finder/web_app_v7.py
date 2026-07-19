from __future__ import annotations

import copy
import json
import math
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import jsonify, render_template, request

from . import web_app as base
from . import web_app_v3 as editable_settings
from . import web_app_v6 as previous
from .crawler_591_multi import MultiPage591ResaleCrawler
from .crawler_591_presale import SECTION_IDS as LEGACY_SECTION_IDS
from .crawler_591_presale_multi import MultiDistrict591PresaleCrawler
from .kaohsiung_districts import ALL_DISTRICTS, DISTRICT_GROUPS, SECTION_IDS
from .listing_history import annotate_history
from .storage import atomic_write_json
from .user_models import HomeListing
from .user_ranking_v6 import evaluate_all


CACHE_TTL_SECONDS = 3 * 24 * 60 * 60
DIAGNOSTICS_PATH = base.BASE_DIR / "data" / "search_diagnostics.json"
HISTORY_PATH = base.BASE_DIR / "data" / "listing_history.json"

editable_settings.ALLOWED_DISTRICTS = set(ALL_DISTRICTS)
LEGACY_SECTION_IDS.update(SECTION_IDS)


class _TimedCache:
    cache_expired = False

    def _load_cache(self) -> dict[str, dict]:
        if self.cache_path.exists():
            age = time.time() - self.cache_path.stat().st_mtime
            if age >= CACHE_TTL_SECONDS:
                self.cache_expired = True
                return {}
        return super()._load_cache()


class TimedResaleCrawler(_TimedCache, MultiPage591ResaleCrawler):
    pass


class TimedPresaleCrawler(_TimedCache, MultiDistrict591PresaleCrawler):
    pass


def load_settings() -> dict:
    return previous.load_settings()


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    atomic_write_json(path, payload)


def _data_completeness(card: dict[str, Any]) -> int:
    missing = len(card.get("questions", []))
    return max(0, 100 - missing * 25)


def _ideal_score(card: dict[str, Any], settings: dict) -> int:
    profile = card["profile"]
    config = settings["profiles"][profile]
    price = float(card.get("price") or 0)
    target = float(config["target_price"])
    maximum = float(config["max_price"])

    if profile == "透天別墅":
        score = 45 if price and price <= target else max(
            0, 45 * (maximum - price) / max(maximum - target, 1)
        )
        age = card.get("age")
        score += 30 if age is not None and age <= 10 else 20 if age is not None and age <= config["preferred_max_age"] else 0
        score += 25 if any("花園" in text or "庭院" in text for text in card.get("strengths", [])) else 0
        return round(max(0, min(100, score)))

    price_weight = 60 if profile == "預售屋" else 35
    score = price_weight if price and price <= target else max(
        0, price_weight * (maximum - price) / max(maximum - target, 1)
    )
    baths = card.get("baths")
    preferred_baths = float(config.get("preferred_min_baths", 2))
    bath_weight = 40 if profile == "預售屋" else 20
    if baths is not None:
        score += bath_weight * min(float(baths) / preferred_baths, 1)
    if profile == "大樓公寓華廈":
        age = card.get("age")
        score += 20 if age is not None and age <= 10 else 14 if age is not None and age <= config["preferred_max_age"] else 0
        floor = card.get("floor")
        total = card.get("total_floors")
        if floor is not None and total:
            ratio = float(floor) / float(total)
            score += 25 if floor == total else 20 if ratio >= 2 / 3 else 10 if ratio >= 0.6 else 0
    return round(max(0, min(100, score)))


def _add_display_metrics(payload: dict[str, Any]) -> dict[str, Any]:
    settings = load_settings()
    for status, cards in payload.get("groups", {}).items():
        for card in cards:
            if status in {"exact_match", "acceptable", "qualified"}:
                card["metric_label"] = "理想條件符合度"
                card["metric_value"] = _ideal_score(card, settings)
            elif status == "needs_verification":
                card["metric_label"] = "資料完整度"
                card["metric_value"] = _data_completeness(card)
            else:
                card["metric_label"] = "未通過必要條件"
                card["metric_value"] = None
    payload["district_groups"] = DISTRICT_GROUPS
    payload["search_diagnostics"] = _load_json(DIAGNOSTICS_PATH)
    return payload


def build_dashboard_payload(records: list[dict[str, Any]]) -> dict[str, Any]:
    return _add_display_metrics(previous.build_dashboard_payload(records))


def load_dashboard_payload() -> dict[str, Any]:
    if not base.RESULTS_PATH.exists():
        return build_dashboard_payload([])
    return build_dashboard_payload(
        json.loads(base.RESULTS_PATH.read_text(encoding="utf-8"))
    )


def _crawl_for_mode(
    profile: str, settings: dict, source: dict, mode: str
) -> tuple[list[HomeListing], dict[str, Any]]:
    search = copy.deepcopy(settings["search"])
    if mode == "full":
        search["pages"] = 10
        search["publish_days"] = 30
    delay = max(2.0, float(source.get("delay_seconds", 2)))
    started = time.time()
    if profile == "預售屋":
        crawler = TimedPresaleCrawler(
            districts=settings["districts"],
            max_details=search["presale_details"],
            delay_seconds=delay,
            headless=True,
        )
    else:
        crawler = TimedResaleCrawler(
            profile=profile,
            districts=settings["districts"],
            max_pages=search["pages"],
            publish_days=search["publish_days"],
            max_details=search["resale_details"],
            delay_seconds=delay,
            headless=True,
        )
    listings = crawler.fetch()
    stats = {
        "profile": profile,
        "mode": mode,
        "district_count": len(settings["districts"]),
        "districts": settings["districts"],
        "pages_requested": None if profile == "預售屋" else search["pages"],
        "publish_days": search["publish_days"],
        "details_limit": search["presale_details"] if profile == "預售屋" else search["resale_details"],
        "fetched": len(listings),
        "detail_failures": sum(item.lifecycle_status == "possibly_removed" for item in listings),
        "cache_expired": bool(crawler.cache_expired),
        "duration_seconds": round(time.time() - started, 1),
        "finished_at": datetime.now(timezone.utc).isoformat(),
    }
    return listings, stats


def _full_scan_merge(
    existing: list[HomeListing], fetched: list[HomeListing], profile: str
) -> tuple[list[HomeListing], int]:
    history = _load_json(HISTORY_PATH)
    fetched_keys = {(item.source, item.external_id) for item in fetched}
    merged: dict[tuple[str, str], HomeListing] = {}
    archived = 0

    for item in existing:
        if previous.previous._listing_profile(item) != profile:
            merged[(item.source, item.external_id)] = item
            continue
        if (item.source, item.external_id) in fetched_keys:
            continue
        entry = history.setdefault(item.external_id, {})
        misses = int(entry.get("missed_full_scans", 0)) + 1
        entry["missed_full_scans"] = misses
        if misses >= 2:
            entry["lifecycle_status"] = "possibly_removed"
            archived += 1
            continue
        item.lifecycle_status = "possibly_removed"
        if "本次完整盤點未再次發現" not in item.data_warnings:
            item.data_warnings.append("本次完整盤點未再次發現")
        merged[(item.source, item.external_id)] = item

    for item in fetched:
        item.search_profile = profile
        merged[(item.source, item.external_id)] = item
        entry = history.setdefault(item.external_id, {})
        entry["missed_full_scans"] = 0
        entry["lifecycle_status"] = item.lifecycle_status
    _write_json(HISTORY_PATH, history)
    return list(merged.values()), archived


def _full_scan_archive_skip_reason(
    existing: list[HomeListing],
    fetched: list[HomeListing],
    profile: str,
    diagnostics: dict[str, Any],
) -> str | None:
    existing_count = sum(
        previous.previous._listing_profile(item) == profile for item in existing
    )
    if not existing_count:
        return None
    if not fetched:
        return "完整盤點未讀取到任何房源"
    minimum_expected = max(1, math.ceil(existing_count * 0.25))
    if existing_count >= 4 and len(fetched) < minimum_expected:
        return (
            f"完整盤點讀取量異常偏低（{len(fetched)}/{existing_count}）"
        )
    detail_failures = int(diagnostics.get("detail_failures") or 0)
    if detail_failures >= len(fetched):
        return "本次讀取的房源詳情全部失敗"
    return None


def _merge_full_scan_safely(
    existing: list[HomeListing],
    fetched: list[HomeListing],
    profile: str,
    diagnostics: dict[str, Any],
) -> tuple[list[HomeListing], int, str | None]:
    reason = _full_scan_archive_skip_reason(existing, fetched, profile, diagnostics)
    if reason:
        preserved = previous.merge_search_results(existing, fetched, profile, "daily")
        return preserved, 0, reason
    listings, archived = _full_scan_merge(existing, fetched, profile)
    return listings, archived, None


def _run_search(profile: str, mode: str) -> None:
    try:
        settings = load_settings()
        config = json.loads(base.CONFIG_PATH.read_text(encoding="utf-8"))
        mode_label = "完整盤點" if mode == "full" else "每日更新"
        base._update_state(
            phase="crawling",
            active_profile=profile,
            search_mode=mode,
            message=f"正在執行「{profile}」{mode_label}…",
        )
        fetched, diagnostics = _crawl_for_mode(profile, settings, config["source"], mode)
        fetched = annotate_history(fetched, path=HISTORY_PATH)
        existing = previous.previous._load_existing_listings()
        archived = 0
        archive_skip_reason: str | None = None
        if mode == "full":
            listings, archived, archive_skip_reason = _merge_full_scan_safely(
                existing, fetched, profile, diagnostics
            )
        else:
            listings = previous.merge_search_results(existing, fetched, profile, mode)

        base._update_state(phase="ranking", message="正在整理有效房源與資料完整度…")
        records = [item.to_dict() for item in evaluate_all(listings, settings)]
        previous._write_results(records)
        diagnostics["archived_after_two_misses"] = archived
        diagnostics["archiving_skipped"] = archive_skip_reason is not None
        if archive_skip_reason:
            diagnostics["archive_skip_reason"] = archive_skip_reason
        else:
            diagnostics.pop("archive_skip_reason", None)
        all_diagnostics = _load_json(DIAGNOSTICS_PATH)
        all_diagnostics[profile] = diagnostics
        _write_json(DIAGNOSTICS_PATH, all_diagnostics)

        insight = build_dashboard_payload(records)["profile_insights"][profile]
        status_note = (
            "；抓取異常，未更新可能下架狀態" if archive_skip_reason else ""
        )
        base._update_state(
            running=False,
            phase="complete",
            active_profile=profile,
            search_mode=mode,
            message=(
                f"{profile}{mode_label}完成：{insight['exact_match']} 組完全符合、"
                f"{insight['acceptable']} 組可接受、本次讀取 {len(fetched)} 筆"
                f"{status_note}"
            ),
            finished_at=base._iso_now(),
            error=None,
        )
    except Exception as exc:  # pragma: no cover
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


def index_v7():
    html = render_template("dashboard_v3.html")
    assets = "".join(
        f'<link rel="stylesheet" href="/static/dashboard_v{version}.css">'
        for version in (4, 5, 6, 7)
    ) + "".join(
        f'<script src="/static/dashboard_v{version}.js" defer></script>'
        for version in (4, 5, 6, 7)
    )
    return html.replace("</head>", '<link rel="icon" href="data:,"' + ">" + assets + "</head>")


def api_results_v7():
    try:
        return jsonify(load_dashboard_payload())
    except (OSError, json.JSONDecodeError) as exc:
        return jsonify({"error": f"無法讀取現有結果：{exc}"}), 500


def api_settings_post_v7():
    if base._state_snapshot()["running"]:
        return jsonify({"error": "搜尋進行中，完成後才能調整條件"}), 409
    try:
        settings = previous.previous.validate_settings(request.get_json(silent=True) or {})
        previous.previous.save_settings(settings)
        previous.re_evaluate_existing(settings)
        return jsonify({"settings": settings, "results": load_dashboard_payload()})
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        return jsonify({"error": str(exc)}), 400


def api_search_v7():
    payload = request.get_json(silent=True) or {}
    profile = payload.get("profile")
    mode = payload.get("mode", "daily")
    if profile not in previous.PROFILES:
        return jsonify({"error": "請先選擇要搜尋的目標"}), 400
    if mode not in previous.SEARCH_MODES:
        return jsonify({"error": "搜尋模式不正確"}), 400
    with base._state_lock:
        if base._state["running"]:
            return jsonify(dict(base._state)), 409
        base._state.update(
            running=True, phase="starting", active_profile=profile,
            search_mode=mode, message=f"準備搜尋「{profile}」…",
            started_at=base._iso_now(), finished_at=None, error=None,
        )
        snapshot = dict(base._state)
    threading.Thread(target=_run_search, args=(profile, mode), daemon=True).start()
    return jsonify(snapshot), 202


app.view_functions["index"] = index_v7
app.view_functions["api_results"] = api_results_v7
app.view_functions["api_settings_post"] = api_settings_post_v7
app.view_functions["api_search"] = api_search_v7
base.load_dashboard_payload = load_dashboard_payload


def main() -> None:
    base.main()


if __name__ == "__main__":
    main()
