from __future__ import annotations

import copy
import json
import threading
from pathlib import Path
from typing import Any

from flask import jsonify, request

from . import web_app_v7 as previous
from .storage import atomic_write_json


app = previous.app
base = previous.base
FAVORITES_PATH = base.BASE_DIR / "data" / "favorites.json"
_favorites_lock = threading.Lock()
_load_previous_dashboard_payload = previous.load_dashboard_payload
_index_v7 = previous.index_v7


def _favorite_key(source: Any, external_id: Any) -> str:
    return f"{str(source or '591').strip()}:{str(external_id or '').strip()}"


def _load_favorite_items(path: Path | None = None) -> list[dict[str, Any]]:
    path = path or FAVORITES_PATH
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("收藏檔格式損壞，已停止寫入以保留原檔") from exc
    if isinstance(payload, dict):
        payload = payload.get("items", [])
    if not isinstance(payload, list):
        raise ValueError("收藏檔格式不正確，已停止寫入以保留原檔")
    return [item for item in payload if isinstance(item, dict) and item.get("id")]


def _write_favorite_items(items: list[dict[str, Any]]) -> None:
    atomic_write_json(FAVORITES_PATH, {"version": 2, "items": items})


def _current_cards(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    cards: dict[str, dict[str, Any]] = {}
    groups = payload.get("groups", {})
    preferred_statuses = (
        "exact_match",
        "acceptable",
        "needs_verification",
        "near_match",
        "rejected",
    )
    for status in preferred_statuses:
        for card in groups.get(status, []):
            key = _favorite_key(card.get("source"), card.get("id"))
            cards.setdefault(key, card)
    return cards


def _storage_snapshot(card: dict[str, Any], saved_at: str) -> dict[str, Any]:
    snapshot = copy.deepcopy(card)
    for field in (
        "is_favorite",
        "favorite_saved_at",
        "favorite_last_seen_at",
        "favorite_is_current",
        "favorite_changes",
        "favorite_change_history",
        "favorite_change_detected_at",
        "change_history",
    ):
        snapshot.pop(field, None)
    snapshot["source"] = snapshot.get("source") or "591"
    snapshot["saved_at"] = saved_at
    return snapshot


_FAVORITE_CHANGE_FIELDS = (
    ("price", "總價", " 萬"),
    ("parking", "車位", ""),
    ("title", "標題", ""),
    ("main_area", "主建物", " 坪"),
    ("rooms", "房數", " 房"),
    ("baths", "衛浴", " 衛"),
    ("floor", "所在樓層", " 樓"),
    ("total_floors", "總樓層", " 樓"),
    ("age", "屋齡", " 年"),
    ("district", "行政區", ""),
)


def _change_value(value: Any, suffix: str) -> str:
    if value is None or value == "":
        return "待確認"
    if suffix:
        try:
            return f"{float(value):g}{suffix}"
        except (TypeError, ValueError):
            pass
    return str(value)


def _favorite_changes(
    stored: dict[str, Any], current: dict[str, Any]
) -> list[str]:
    changes: list[str] = []
    for field, label, suffix in _FAVORITE_CHANGE_FIELDS:
        if field not in stored:
            continue
        before = stored.get(field)
        after = current.get(field)
        if before != after:
            changes.append(
                f"{label}：{_change_value(before, suffix)} → "
                f"{_change_value(after, suffix)}"
            )
    return changes


def _favorite_history(stored: dict[str, Any]) -> list[dict[str, Any]]:
    history = stored.get("change_history", [])
    if not isinstance(history, list):
        return []
    return [
        copy.deepcopy(entry)
        for entry in history
        if isinstance(entry, dict) and isinstance(entry.get("changes"), list)
    ]


def _decorate_favorite_changes(
    card: dict[str, Any], history: list[dict[str, Any]]
) -> None:
    card["favorite_change_history"] = copy.deepcopy(history)
    latest = history[-1] if history else {}
    card["favorite_changes"] = copy.deepcopy(latest.get("changes", []))
    card["favorite_change_detected_at"] = latest.get("detected_at")


def _copy_availability(stored: dict[str, Any], card: dict[str, Any]) -> None:
    for field in (
        "availability_status",
        "availability_checked_at",
        "availability_reason",
        "availability_history",
        "removed_at",
        "favorite_note",
        "favorite_note_updated_at",
    ):
        if field in stored:
            card[field] = stored[field]


def _decorate_with_favorites(
    payload: dict[str, Any], *, refresh_snapshots: bool = True
) -> dict[str, Any]:
    items = _load_favorite_items()
    favorites_by_key = {
        _favorite_key(item.get("source"), item.get("id")): item
        for item in items
    }
    for cards in payload.get("groups", {}).values():
        for card in cards:
            stored = favorites_by_key.get(
                _favorite_key(card.get("source"), card.get("id"))
            )
            card["is_favorite"] = stored is not None
            if stored is not None:
                card["favorite_saved_at"] = stored.get("saved_at")
                card["favorite_last_seen_at"] = card.get("last_seen_at")
                card["favorite_is_current"] = True

    current = _current_cards(payload)
    rendered: list[dict[str, Any]] = []
    refreshed: list[dict[str, Any]] = []
    changed = False
    for stored in items:
        key = _favorite_key(stored.get("source"), stored.get("id"))
        saved_at = str(stored.get("saved_at") or base._iso_now())
        current_card = current.get(key)
        history = _favorite_history(stored)
        if current_card:
            changes = _favorite_changes(stored, current_card)
            if changes:
                history.append({
                    "detected_at": base._iso_now(),
                    "changes": changes,
                })
                history = history[-50:]
            stored_card = _storage_snapshot(current_card, saved_at)
            if history:
                stored_card["change_history"] = history
            _copy_availability(stored, stored_card)
            changed = changed or stored_card != stored
            refreshed.append(stored_card)
            _decorate_favorite_changes(current_card, history)
            _copy_availability(stored, current_card)
            card = copy.deepcopy(current_card)
            card["favorite_is_current"] = True
        else:
            refreshed.append(stored)
            card = copy.deepcopy(stored)
            card.pop("saved_at", None)
            card["favorite_is_current"] = False
            _decorate_favorite_changes(card, history)
        card["is_favorite"] = True
        card["favorite_saved_at"] = saved_at
        card["favorite_last_seen_at"] = card.get("last_seen_at")
        rendered.append(card)

    if changed and refresh_snapshots:
        _write_favorite_items(refreshed)
    rendered.sort(key=lambda item: str(item.get("favorite_saved_at") or ""), reverse=True)
    payload["favorites"] = rendered
    payload.setdefault("summary", {})["favorites"] = len(rendered)
    return payload


def load_dashboard_payload() -> dict[str, Any]:
    with _favorites_lock:
        return _decorate_with_favorites(_load_previous_dashboard_payload())


def index_v8():
    html = _index_v7()
    assets = (
        '<link rel="stylesheet" href="/static/dashboard_v8.css">'
        '<script src="/static/dashboard_v8.js" defer></script>'
    )
    return html.replace("</head>", assets + "</head>")


def api_results_v8():
    try:
        return jsonify(load_dashboard_payload())
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        return jsonify({"error": f"無法讀取收藏或現有結果：{exc}"}), 500
    except Exception:
        app.logger.exception("Unexpected failure while loading favorites")
        return jsonify({"error": "收藏服務發生未預期錯誤，請重新整理後再試。"}), 500


@app.post("/api/favorites")
def api_favorites_v8():
    body = request.get_json(silent=True) or {}
    source = str(body.get("source") or "591").strip()
    external_id = str(body.get("id") or "").strip()
    action = body.get("action", "add")
    if not external_id:
        return jsonify({"error": "缺少房源編號"}), 400
    if action not in {"add", "remove"}:
        return jsonify({"error": "收藏操作不正確"}), 400

    with _favorites_lock:
        try:
            items = _load_favorite_items()
        except (ValueError, OSError) as exc:
            return jsonify({"error": f"無法讀取收藏：{exc}"}), 500
        key = _favorite_key(source, external_id)
        existing = {
            _favorite_key(item.get("source"), item.get("id")): item
            for item in items
        }
        if action == "remove":
            items = [
                item
                for item in items
                if _favorite_key(item.get("source"), item.get("id")) != key
            ]
            _write_favorite_items(items)
        else:
            dashboard = _load_previous_dashboard_payload()
            card = _current_cards(dashboard).get(key)
            if card is None:
                return jsonify({"error": "目前結果中找不到這筆房源，請重新整理後再試。"}), 404
            saved_at = str(existing.get(key, {}).get("saved_at") or base._iso_now())
            snapshot = _storage_snapshot(card, saved_at)
            change_history = _favorite_history(existing.get(key, {}))
            if change_history:
                snapshot["change_history"] = change_history
            _copy_availability(existing.get(key, {}), snapshot)
            items = [
                item
                for item in items
                if _favorite_key(item.get("source"), item.get("id")) != key
            ]
            items.append(snapshot)
            _write_favorite_items(items)

        result = _decorate_with_favorites(
            _load_previous_dashboard_payload(), refresh_snapshots=False
        )
    return jsonify(result)


def activate() -> None:
    app.view_functions["index"] = index_v8
    app.view_functions["api_results"] = api_results_v8
    previous.load_dashboard_payload = load_dashboard_payload
    base.load_dashboard_payload = load_dashboard_payload


def main() -> None:
    activate()
    base.main()


if __name__ == "__main__":
    main()
