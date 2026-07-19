from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Listing:
    id: str
    title: str
    url: str
    city: str
    district: str
    total_price_wan: float
    area_ping: float
    rooms: float
    age_years: float | None = None
    floor: str | None = None
    address: str | None = None
    tags: tuple[str, ...] = ()
    source: str = "unknown"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Listing":
        values = dict(data)
        values["tags"] = tuple(values.get("tags", ()))
        return cls(**values)

    @property
    def price_per_ping_wan(self) -> float:
        return self.total_price_wan / self.area_ping if self.area_ping else 0.0

    @property
    def searchable_text(self) -> str:
        return " ".join(
            part
            for part in (
                self.title,
                self.city,
                self.district,
                self.address or "",
                " ".join(self.tags),
            )
            if part
        ).lower()


@dataclass(frozen=True)
class Preferences:
    cities: tuple[str, ...] = ()
    districts: tuple[str, ...] = ()
    max_total_price_wan: float | None = None
    min_area_ping: float | None = None
    min_rooms: float | None = None
    max_age_years: float | None = None
    required_keywords: tuple[str, ...] = ()
    excluded_keywords: tuple[str, ...] = ()
    preferred_keywords: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Preferences":
        values = dict(data)
        for key in (
            "cities",
            "districts",
            "required_keywords",
            "excluded_keywords",
            "preferred_keywords",
        ):
            values[key] = tuple(values.get(key, ()))
        return cls(**values)


@dataclass(frozen=True)
class RankedListing:
    listing: Listing
    score: float
    reasons: tuple[str, ...] = field(default_factory=tuple)
