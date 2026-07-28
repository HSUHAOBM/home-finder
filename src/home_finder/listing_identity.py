from __future__ import annotations

from typing import Any

from .user_models import HomeListing


def source_listing_key(source: Any, external_id: Any) -> tuple[str, str]:
    return (
        str(source or "unknown").strip(),
        str(external_id or "").strip(),
    )


def source_listing_ref(source: Any, external_id: Any) -> str:
    source_name, listing_id = source_listing_key(source, external_id)
    return f"{source_name}:{listing_id}"


def listing_history_key(listing: HomeListing) -> str:
    return source_listing_ref(listing.source, listing.external_id)


def canonical_listing_key(listing: HomeListing) -> tuple[str, str]:
    if listing.origin_source and listing.origin_external_id:
        return source_listing_key(listing.origin_source, listing.origin_external_id)
    return source_listing_key(listing.source, listing.external_id)
