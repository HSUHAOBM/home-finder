from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from .models import Listing


class ListingSource(Protocol):
    def fetch(self) -> list[Listing]: ...


class JsonFileSource:
    """本機 JSON 資料源，用來獨立驗證篩選與評分邏輯。"""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def fetch(self) -> list[Listing]:
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise ValueError("房源 JSON 最外層必須是陣列")
        return [Listing.from_dict(item) for item in raw]
