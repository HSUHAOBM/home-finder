from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


Status = Literal["qualified", "needs_verification", "rejected"]
ProfileName = Literal["大樓公寓華廈", "透天別墅", "預售屋"]


@dataclass
class HomeListing:
    source: str
    external_id: str
    title: str
    url: str
    city: str
    district: str
    total_price_wan: float
    deal_kind: str = "中古屋"
    property_type: str | None = None
    total_area_ping: float | None = None
    main_area_ping: float | None = None
    rooms: float | None = None
    living_rooms: float | None = None
    baths: float | None = None
    age_years: float | None = None
    current_floor: int | None = None
    total_floors: int | None = None
    community: str | None = None
    address: str | None = None
    parking_type: str | None = None
    has_parking: bool | None = None
    has_garden: bool | None = None
    tags: list[str] = field(default_factory=list)
    data_warnings: list[str] = field(default_factory=list)
    search_profile: str | None = None
    listing_updated_text: str | None = None
    first_seen_at: str | None = None
    last_seen_at: str | None = None
    lifecycle_status: str | None = None
    origin_source: str | None = None
    origin_external_id: str | None = None
    broker_name: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HomeListing":
        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def floor_ratio(self) -> float | None:
        if self.current_floor is None or not self.total_floors:
            return None
        return self.current_floor / self.total_floors


@dataclass
class Evaluation:
    listing: HomeListing
    profile: ProfileName
    status: Status
    score: float
    hard_failures: list[str] = field(default_factory=list)
    missing_required: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    concerns: list[str] = field(default_factory=list)
    duplicate_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        return result
