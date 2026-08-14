from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .storage import atomic_write_json
from .user_models import HomeListing


MISCLASSIFICATION_MARKER = "依集合住宅排除"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _key(source: str, broker_name: str) -> str:
    normalized = "".join(broker_name.split()).casefold()
    return f"{source}::{normalized}"


def load_watchlist(path: str | Path) -> dict[str, Any]:
    target = Path(path)
    if not target.exists():
        return {"version": 1, "brokers": {}}
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "brokers": {}}
    if not isinstance(payload, dict) or not isinstance(payload.get("brokers"), dict):
        return {"version": 1, "brokers": {}}
    return payload


def update_watchlist(
    listings: list[HomeListing], path: str | Path
) -> dict[str, Any]:
    payload = load_watchlist(path)
    brokers = payload["brokers"]
    changed = False
    detected_at = _now()
    for listing in listings:
        if not listing.broker_name:
            continue
        reasons = [
            warning
            for warning in listing.data_warnings
            if MISCLASSIFICATION_MARKER in warning
        ]
        if not reasons:
            continue
        key = _key(listing.source, listing.broker_name)
        entry = brokers.setdefault(
            key,
            {
                "source": listing.source,
                "broker_name": listing.broker_name,
                "first_flagged_at": detected_at,
                "last_flagged_at": detected_at,
                "incidents": [],
            },
        )
        incidents = entry.setdefault("incidents", [])
        incident = next(
            (
                item
                for item in incidents
                if str(item.get("listing_id")) == str(listing.external_id)
            ),
            None,
        )
        if incident is None:
            incidents.append(
                {
                    "listing_id": listing.external_id,
                    "title": listing.title,
                    "url": listing.url,
                    "reason": reasons[0],
                    "detected_at": detected_at,
                }
            )
            changed = True
        entry["last_flagged_at"] = detected_at
        entry["incident_count"] = len(incidents)
    if changed:
        atomic_write_json(path, payload)
    return payload


def broker_alert(
    source: str | None, broker_name: str | None, watchlist: dict[str, Any]
) -> dict[str, Any] | None:
    if not source or not broker_name:
        return None
    entry = watchlist.get("brokers", {}).get(_key(source, broker_name))
    if not entry:
        return None
    incidents = entry.get("incidents", [])
    return {
        "broker_name": entry.get("broker_name") or broker_name,
        "incident_count": len(incidents),
        "last_flagged_at": entry.get("last_flagged_at"),
        "incidents": incidents,
    }
