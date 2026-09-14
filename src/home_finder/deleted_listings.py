from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .listing_identity import source_listing_ref
from .storage import atomic_write_json
from .user_models import HomeListing


def _empty() -> dict[str, Any]:
    return {"version": 1, "items": {}}


def load_deleted_listings(path: str | Path) -> dict[str, Any]:
    target = Path(path)
    if not target.exists():
        return _empty()
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _empty()
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), dict):
        return _empty()
    return payload


def record_deleted_listings(
    path: str | Path,
    cards: Iterable[dict[str, Any]],
    *,
    reason: str,
    deleted_at: str | None = None,
) -> set[str]:
    payload = load_deleted_listings(path)
    timestamp = deleted_at or datetime.now(timezone.utc).isoformat()
    keys: set[str] = set()
    for card in cards:
        key = source_listing_ref(card.get("source"), card.get("id"))
        if key.endswith(":"):
            continue
        previous = payload["items"].get(key, {})
        events = previous.get("events", []) if isinstance(previous, dict) else []
        if not isinstance(events, list):
            events = []
        events.append({"action": "deleted", "at": timestamp, "reason": reason})
        payload["items"][key] = {
            "state": "deleted",
            "source": card.get("source"),
            "id": str(card.get("id")),
            "title": card.get("title"),
            "url": card.get("url"),
            "profile": card.get("profile"),
            "status": card.get("status"),
            "snapshot": card,
            "events": events[-20:],
        }
        keys.add(key)
    atomic_write_json(Path(path), payload)
    return keys


def reconcile_relisted(
    listings: list[HomeListing],
    path: str | Path,
    *,
    relisted_at: str | None = None,
) -> list[HomeListing]:
    payload = load_deleted_listings(path)
    timestamp = relisted_at or datetime.now(timezone.utc).isoformat()
    changed = False
    for listing in listings:
        key = source_listing_ref(listing.source, listing.external_id)
        entry = payload["items"].get(key)
        if not isinstance(entry, dict) or entry.get("state") != "deleted":
            continue
        listing.lifecycle_status = "relisted"
        note = "先前已從結果刪除，本次搜尋重新上架"
        if note not in listing.data_warnings:
            listing.data_warnings.append(note)
        events = entry.get("events", [])
        if not isinstance(events, list):
            events = []
        events.append({"action": "relisted", "at": timestamp})
        entry.update(state="relisted", relisted_at=timestamp, events=events[-20:])
        changed = True
    if changed:
        atomic_write_json(Path(path), payload)
    return listings
