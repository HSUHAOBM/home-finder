from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .user_models import HomeListing


def append_crawl_audit(
    path: str | Path,
    listings: Iterable[HomeListing],
    *,
    profile: str,
    mode: str,
    saved_to: str,
    crawled_at: str | None = None,
) -> int:
    """Append one searchable JSON line for every successfully stored crawl result."""
    audit_path = Path(path)
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = crawled_at or datetime.now(timezone.utc).isoformat()
    count = 0
    with audit_path.open("a", encoding="utf-8", newline="\n") as handle:
        for listing in listings:
            record = {
                "crawled_at": timestamp,
                "source": listing.source,
                "profile": profile,
                "mode": mode,
                "external_id": listing.external_id,
                "url": listing.url,
                "title": listing.title,
                "total_price_wan": listing.total_price_wan,
                "district": listing.district,
                "saved_to": saved_to,
                "result": "stored",
            }
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
            handle.write("\n")
            count += 1
    return count
