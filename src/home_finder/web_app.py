from __future__ import annotations

import argparse
import json
import os
import threading
import webbrowser
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, render_template

from .crawler_591_browser_v3 import Browser591Crawler
from .listing_identity import source_listing_ref
from .crawler_591_presale_v2 import Browser591PresaleCrawler
from .make_report import render_report
from .result_store import read_result_records
from .user_ranking_v3 import evaluate_all


BASE_DIR = Path(__file__).resolve().parents[2]
CONFIG_PATH = BASE_DIR / "config.user.json"
RESULTS_PATH = BASE_DIR / "output" / "current-results.json"
SUMMARY_PATH = BASE_DIR / "output" / "current-summary.md"

app = Flask(__name__)
_state_lock = threading.Lock()
_state: dict[str, Any] = {
    "running": False,
    "phase": "idle",
    "message": "可以開始搜尋",
    "started_at": None,
    "finished_at": None,
    "error": None,
    "service_instance": datetime.now(timezone.utc).isoformat(),
}


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _update_state(**changes: Any) -> None:
    with _state_lock:
        _state.update(changes)


def _state_snapshot() -> dict[str, Any]:
    with _state_lock:
        return dict(_state)


def _preferred_profile(listing: dict[str, Any]) -> str:
    if listing.get("deal_kind") == "預售屋":
        return "預售屋"
    property_type = listing.get("property_type") or ""
    if "透天" in property_type or "別墅" in property_type:
        return "透天別墅"
    return "大樓公寓華廈"


def select_listing_results(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """每個房源只保留最符合其實際建物類型的那套評估。"""
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        listing = record.get("listing", {})
        external_id = str(listing.get("external_id", ""))
        if external_id:
            grouped[
                source_listing_ref(listing.get("source"), external_id)
            ].append(record)

    status_order = {"qualified": 0, "needs_verification": 1, "rejected": 2}
    selected: list[dict[str, Any]] = []
    for candidates in grouped.values():
        expected = _preferred_profile(candidates[0]["listing"])
        matching = [item for item in candidates if item.get("profile") == expected]
        pool = matching or candidates
        best = min(
            pool,
            key=lambda item: (
                status_order.get(item.get("status", "rejected"), 9),
                -float(item.get("score", 0)),
            ),
        )
        selected.append(best)

    return sorted(
        selected,
        key=lambda item: (
            status_order.get(item.get("status", "rejected"), 9),
            -float(item.get("score", 0)),
            float(item.get("listing", {}).get("total_price_wan") or 999999),
        ),
    )


def _card(record: dict[str, Any]) -> dict[str, Any]:
    listing = record["listing"]
    return {
        "id": listing.get("external_id"),
        "source": listing.get("source") or "591",
        "origin_source": listing.get("origin_source"),
        "origin_id": listing.get("origin_external_id"),
        "broker_name": listing.get("broker_name"),
        "status": record.get("status"),
        "profile": record.get("profile"),
        "score": record.get("score"),
        "title": listing.get("title"),
        "url": listing.get("url"),
        "district": listing.get("district"),
        "price": listing.get("total_price_wan") or None,
        "main_area": listing.get("main_area_ping"),
        "rooms": listing.get("rooms"),
        "baths": listing.get("baths"),
        "parking": listing.get("parking_type"),
        "floor": listing.get("current_floor"),
        "total_floors": listing.get("total_floors"),
        "age": listing.get("age_years"),
        "strengths": record.get("strengths", []),
        "questions": record.get("missing_required", []),
        "concerns": record.get("concerns", []),
        "failures": record.get("hard_failures", []),
        "duplicates": record.get("duplicate_ids", []),
    }


def build_dashboard_payload(records: list[dict[str, Any]]) -> dict[str, Any]:
    selected = select_listing_results(records)
    groups = {"qualified": [], "needs_verification": [], "rejected": []}
    failure_counts: Counter[str] = Counter()
    for record in selected:
        status = record.get("status", "rejected")
        groups.setdefault(status, []).append(_card(record))
        if status == "rejected":
            failure_counts.update(record.get("hard_failures", []))

    updated_at = None
    if RESULTS_PATH.exists():
        updated_at = datetime.fromtimestamp(
            RESULTS_PATH.stat().st_mtime, tz=timezone.utc
        ).isoformat()
    return {
        "updated_at": updated_at,
        "summary": {
            "total": len(selected),
            "qualified": len(groups["qualified"]),
            "needs_verification": len(groups["needs_verification"]),
            "rejected": len(groups["rejected"]),
        },
        "groups": groups,
        "rejection_reasons": [
            {"reason": reason, "count": count}
            for reason, count in failure_counts.most_common(12)
        ],
    }


def load_dashboard_payload() -> dict[str, Any]:
    if not RESULTS_PATH.exists():
        return build_dashboard_payload([])
    records = read_result_records(RESULTS_PATH)
    return build_dashboard_payload(records)


def _run_search() -> None:
    try:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        source = config["source"]
        districts = source["districts"]
        delay = max(2.0, float(source.get("delay_seconds", 2)))

        _update_state(phase="resale", message="正在讀取 591 中古屋詳情…")
        resale = Browser591Crawler(
            districts=districts,
            max_details=int(source.get("max_details", 20)),
            delay_seconds=delay,
            headless=bool(source.get("headless", True)),
        ).fetch()

        _update_state(phase="presale", message="正在讀取 591 預售屋詳情…")
        presale = Browser591PresaleCrawler(
            districts=districts,
            max_details=int(source.get("presale_max_details", 12)),
            delay_seconds=delay,
            headless=bool(source.get("headless", True)),
        ).fetch()

        _update_state(phase="ranking", message="正在核對條件、排序與去重…")
        results = evaluate_all(resale + presale)
        records = [item.to_dict() for item in results]
        RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        RESULTS_PATH.write_text(
            json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        SUMMARY_PATH.write_text(render_report(records), encoding="utf-8")

        payload = build_dashboard_payload(records)
        summary = payload["summary"]
        _update_state(
            running=False,
            phase="complete",
            message=(
                f"完成：{summary['qualified']} 筆符合、"
                f"{summary['needs_verification']} 筆待確認"
            ),
            finished_at=_iso_now(),
            error=None,
        )
    except Exception as exc:  # pragma: no cover - relies on live website state
        _update_state(
            running=False,
            phase="error",
            message="搜尋未完成，請稍後再試",
            finished_at=_iso_now(),
            error=str(exc),
        )


@app.get("/")
def index():
    return render_template("dashboard_v2.html")


@app.get("/api/results")
def api_results():
    try:
        return jsonify(load_dashboard_payload())
    except (OSError, json.JSONDecodeError) as exc:
        return jsonify({"error": f"無法讀取現有結果：{exc}"}), 500


@app.get("/api/status")
def api_status():
    return jsonify(_state_snapshot())


@app.post("/api/search")
def api_search():
    with _state_lock:
        if _state["running"]:
            return jsonify(dict(_state)), 409
        _state.update(
            running=True,
            phase="starting",
            message="準備開始搜尋…",
            started_at=_iso_now(),
            finished_at=None,
            error=None,
        )
        snapshot = dict(_state)
    threading.Thread(target=_run_search, daemon=True).start()
    return jsonify(snapshot), 202


def _reload_extra_files() -> list[str]:
    watched: list[str] = []
    for folder_name in ("templates", "static"):
        folder = Path(__file__).with_name(folder_name)
        if folder.exists():
            watched.extend(str(path) for path in folder.rglob("*") if path.is_file())
    return watched


def main() -> None:
    parser = argparse.ArgumentParser(description="開啟高雄個人找房介面")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()
    url = f"http://127.0.0.1:{args.port}"
    is_reloader_child = os.environ.get("WERKZEUG_RUN_MAIN") == "true"
    if not args.no_browser and (not args.reload or not is_reloader_child):
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    print(f"找房介面：{url}")
    if args.reload:
        print("自動重載已啟用；程式或頁面檔案變更後會自動重新啟動服務。")
    print("按 Ctrl+C 或關閉這個命令視窗即可停止；搜尋進行中請勿關閉。")
    app.run(
        host="127.0.0.1",
        port=args.port,
        debug=False,
        use_reloader=args.reload,
        extra_files=_reload_extra_files() if args.reload else None,
    )


if __name__ == "__main__":
    main()
