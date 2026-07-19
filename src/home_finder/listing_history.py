from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from .user_models import HomeListing


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
        previous = history.get(listing.external_id)
        if previous is None:
            first_seen = timestamp
            lifecycle = "new"
        else:
            first_seen = previous.get("first_seen_at") or timestamp
            old_update = previous.get("listing_updated_text")
            lifecycle = (
                "updated"
                if listing.listing_updated_text and old_update and listing.listing_updated_text != old_update
                else "seen"
            )
        item = replace(
            listing,
            first_seen_at=first_seen,
            last_seen_at=timestamp,
            lifecycle_status=listing.lifecycle_status or lifecycle,
        )
        annotated.append(item)
        history[listing.external_id] = {
            "title": item.title,
            "url": item.url,
            "search_profile": item.search_profile,
            "first_seen_at": first_seen,
            "last_seen_at": timestamp,
            "listing_updated_text": item.listing_updated_text,
            "lifecycle_status": item.lifecycle_status,
        }

    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    return annotated
