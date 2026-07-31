from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from .storage import atomic_write_json
from .listing_identity import listing_history_key
from .user_models import HomeListing


def _number(value: object) -> str:
    number = float(value)
    return f"{number:g}"


def _history_snapshot(listing: HomeListing) -> dict[str, object]:
    return {
        "title": listing.title,
        "total_price_wan": listing.total_price_wan,
        "main_area_ping": listing.main_area_ping,
        "rooms": listing.rooms,
        "baths": listing.baths,
        "parking_type": listing.parking_type,
        "current_floor": listing.current_floor,
        "total_floors": listing.total_floors,
        "age_years": listing.age_years,
        "community": listing.community,
        "address": listing.address,
    }


def _format_change(field: str, before: object, after: object) -> str:
    labels = {
        "title": "標題",
        "total_price_wan": "總價",
        "main_area_ping": "主建物",
        "rooms": "房數",
        "baths": "衛浴",
        "parking_type": "車位",
        "current_floor": "所在樓層",
        "total_floors": "總樓層",
        "age_years": "屋齡",
        "community": "社區",
        "address": "地址",
    }
    suffixes = {
        "total_price_wan": " 萬",
        "main_area_ping": " 坪",
        "rooms": " 房",
        "baths": " 衛",
        "current_floor": " 樓",
        "total_floors": " 樓",
        "age_years": " 年",
    }

    def display(value: object) -> str:
        if value is None or value == "":
            return "待確認"
        if field in suffixes:
            return f"{_number(value)}{suffixes[field]}"
        return str(value)

    return f"{labels[field]}：{display(before)} → {display(after)}"


def _change_details(previous_snapshot: object, listing: HomeListing) -> list[str]:
    if not isinstance(previous_snapshot, dict):
        return []
    current = _history_snapshot(listing)
    changes: list[str] = []
    for field, after in current.items():
        if field not in previous_snapshot:
            continue
        before = previous_snapshot.get(field)
        if before != after:
            changes.append(_format_change(field, before, after))
    return changes


def _load(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def annotate_history(
    listings: list[HomeListing],
    path: str | Path = "data/listing_history.json",
    now: datetime | None = None,
) -> list[HomeListing]:
    history_path = Path(path)
    history = _load(history_path)
    timestamp = (now or datetime.now(timezone.utc)).isoformat()
    annotated: list[HomeListing] = []

    for listing in listings:
        key = listing_history_key(listing)
        previous = history.get(key)
        if previous is None:
            # Read legacy entries once while migrating to source-aware keys.
            previous = history.get(listing.external_id)
        if previous is None:
            first_seen = timestamp
            lifecycle = "new"
            changes: list[str] = []
        else:
            first_seen = previous.get("first_seen_at") or timestamp
            changes = _change_details(previous.get("snapshot"), listing)
            lifecycle = "updated" if changes else "seen"
        item = replace(
            listing,
            first_seen_at=first_seen,
            last_seen_at=timestamp,
            lifecycle_status=listing.lifecycle_status or lifecycle,
            change_details=changes,
        )
        annotated.append(item)
        history[key] = {
            "source": item.source,
            "external_id": item.external_id,
            "title": item.title,
            "url": item.url,
            "search_profile": item.search_profile,
            "first_seen_at": first_seen,
            "last_seen_at": timestamp,
            "listing_updated_text": item.listing_updated_text,
            "lifecycle_status": item.lifecycle_status,
            "change_details": item.change_details,
            "snapshot": _history_snapshot(item),
        }

    atomic_write_json(history_path, history)
    return annotated
