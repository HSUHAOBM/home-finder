from __future__ import annotations

import json
import zipfile
from typing import Any

from flask import jsonify, request

from . import web_app_v15 as previous
from . import web_app_v8 as favorites_app
from . import web_app_v7 as crawl_app
from .deleted_listings import record_deleted_listings
from .favorite_availability import AvailabilityResult, FavoriteAvailabilityChecker
from .listing_identity import source_listing_ref
from .real_price import query_real_price
from .result_store import read_result_records
from .storage import atomic_write_json


app = previous.app
base = previous.base
_index_v15 = previous.index_v15
REAL_PRICE_CACHE_DIR = base.BASE_DIR / "data" / "cache" / "real-price"
URL_AVAILABILITY_PATH = base.BASE_DIR / "data" / "url_availability.json"
DELETED_LISTINGS_PATH = base.BASE_DIR / "data" / "deleted_listings.json"


def _load_url_availability() -> dict[str, dict[str, str]]:
    if not URL_AVAILABILITY_PATH.exists():
        return {}
    try:
        data = json.loads(URL_AVAILABILITY_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _availability_key(item: dict[str, Any]) -> str:
    return favorites_app._favorite_key(item.get("source"), item.get("id"))


def load_dashboard_payload_v16() -> dict[str, Any]:
    payload = favorites_app.load_dashboard_payload()
    cached = _load_url_availability()
    for cards in [*payload.get("groups", {}).values(), payload.get("favorites", [])]:
        for card in cards:
            status = cached.get(_availability_key(card))
            if status:
                card.update(status)
    return payload


def check_listing_availability(
    item: dict[str, Any], *, checker: FavoriteAvailabilityChecker | None = None
) -> dict[str, str]:
    checked_at = base._iso_now()
    captured: list[AvailabilityResult] = []
    (checker or FavoriteAvailabilityChecker(headless=True)).check_many(
        [item], on_result=lambda _item, result: captured.append(result)
    )
    result = captured[0] if captured else AvailabilityResult("unknown", "查核沒有回傳結果")
    return {
        "url_availability_status": result.status,
        "url_availability_reason": result.reason,
        "url_availability_checked_at": checked_at,
    }


@app.post("/api/listing-availability")
def api_listing_availability_v16():
    body = request.get_json(silent=True) or {}
    source = str(body.get("source") or "").strip()
    external_id = str(body.get("id") or "").strip()
    if not source or not external_id:
        return jsonify({"error": "缺少房源來源或編號。"}), 400

    payload = load_dashboard_payload_v16()
    cards = [
        card
        for group in payload.get("groups", {}).values()
        for card in group
    ]
    target_key = favorites_app._favorite_key(source, external_id)
    listing = next((card for card in cards if _availability_key(card) == target_key), None)
    if listing is None:
        return jsonify({"error": "目前結果中找不到這筆房源。"}), 404
    status = check_listing_availability(listing)
    cached = _load_url_availability()
    cached[target_key] = status
    atomic_write_json(URL_AVAILABILITY_PATH, cached)
    return jsonify(status)


def _all_payload_cards(payload: dict[str, Any]) -> list[dict[str, Any]]:
    cards = [card for group in payload.get("groups", {}).values() for card in group]
    cards.extend(payload.get("favorites", []))
    return cards


@app.post("/api/listings/delete")
def api_delete_listings_v16():
    body = request.get_json(silent=True) or {}
    requested = body.get("items")
    profile = str(body.get("profile") or "")
    category = str(body.get("category") or "")
    removed_only = bool(body.get("removed_only"))
    clear_category = bool(body.get("clear_category"))
    if not isinstance(requested, list) or not requested or len(requested) > 1000:
        return jsonify({"error": "刪除清單不正確。"}), 400
    if clear_category and category != "near_match":
        return jsonify({"error": "目前只允許整批清除差強人意分類。"}), 400

    payload = load_dashboard_payload_v16()
    cards = _all_payload_cards(payload)
    by_key = {_availability_key(card): card for card in cards}
    selected: list[dict[str, Any]] = []
    for value in requested:
        if not isinstance(value, dict):
            return jsonify({"error": "刪除清單不正確。"}), 400
        key = source_listing_ref(value.get("source"), value.get("id"))
        card = by_key.get(key)
        if card is None:
            return jsonify({"error": "刪除清單包含目前頁面不存在的房源。"}), 409
        if category == "favorites":
            if not card.get("is_favorite"):
                return jsonify({"error": "刪除範圍與目前收藏頁不一致。"}), 409
        elif card.get("profile") != profile or card.get("status") != category:
            return jsonify({"error": "刪除範圍與目前分類頁不一致。"}), 409
        if removed_only and (
            card.get("url_availability_status") or card.get("availability_status")
        ) != "removed":
            return jsonify({"error": "批次清單包含未確認下架的房源。"}), 409
        selected.append(card)

    expanded = list(selected)
    for card in selected:
        for variant in card.get("variants", []):
            expanded.append({
                **variant,
                "profile": card.get("profile"),
                "status": card.get("status"),
            })
    deleted_keys = record_deleted_listings(
        DELETED_LISTINGS_PATH,
        expanded,
        reason=(
            "clear_removed_page" if removed_only
            else "clear_category_page" if clear_category
            else "manual_card_delete"
        ),
    )
    records = read_result_records(base.RESULTS_PATH)
    remaining = [
        record for record in records
        if source_listing_ref(
            record.get("listing", {}).get("source"),
            record.get("listing", {}).get("external_id"),
        ) not in deleted_keys
    ]
    crawl_app.previous._write_results(remaining)

    with favorites_app._favorites_lock:
        favorites = favorites_app._load_favorite_items()
        favorites = [
            item for item in favorites
            if source_listing_ref(item.get("source"), item.get("id")) not in deleted_keys
        ]
        favorites_app._write_favorite_items(favorites)
    return jsonify({
        "deleted": len(selected),
        "results": load_dashboard_payload_v16(),
    })


@app.post("/api/favorites/real-price")
def api_favorite_real_price_v16():
    payload = request.get_json(silent=True) or {}
    source = str(payload.get("source") or "").strip()
    external_id = str(payload.get("id") or "").strip()
    months = payload.get("months", 12)
    if not source or not external_id or months not in (6, 12, 60, 120):
        return jsonify({"error": "查詢條件不正確。"}), 400
    favorites = favorites_app.load_dashboard_payload().get("favorites", [])
    key = favorites_app._favorite_key(source, external_id)
    listing = next(
        (item for item in favorites if favorites_app._favorite_key(item.get("source"), item.get("id")) == key),
        None,
    )
    if listing is None:
        return jsonify({"error": "找不到這筆收藏房源。"}), 404
    if not listing.get("district") or not listing.get("address"):
        return jsonify({"error": "這筆收藏缺少行政區或地址，無法比對實價登錄。"}), 400
    try:
        return jsonify(query_real_price(listing, cache_dir=REAL_PRICE_CACHE_DIR, months=months))
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        return jsonify({"error": f"官方資料讀取失敗：{exc}"}), 502
    except Exception:
        app.logger.exception("Unexpected real-price lookup failure")
        return jsonify({"error": "實價登錄查詢失敗，請稍後再試。"}), 502


def index_v16():
    html = _index_v15()
    assets = (
        '<link rel="stylesheet" href="/static/dashboard_v16.css">'
        '<script src="/static/dashboard_v16.js" defer></script>'
    )
    return html.replace("</head>", assets + "</head>")


def activate() -> None:
    previous.activate()
    base.load_dashboard_payload = load_dashboard_payload_v16
    app.view_functions["index"] = index_v16


def main() -> None:
    activate()
    base.main()


if __name__ == "__main__":
    main()
