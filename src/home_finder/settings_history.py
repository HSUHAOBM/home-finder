from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from .storage import atomic_write_json


def load_settings_history(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(payload, list):
        return []
    return [
        entry
        for entry in payload
        if isinstance(entry, dict)
        and isinstance(entry.get("id"), str)
        and isinstance(entry.get("saved_at"), str)
        and isinstance(entry.get("settings"), dict)
    ]


def record_settings_snapshot(
    path: Path, settings: dict[str, Any], saved_at: str
) -> dict[str, Any]:
    history = load_settings_history(path)
    snapshot = copy.deepcopy(settings)
    if history and history[-1]["settings"] == snapshot:
        return history[-1]

    entry = {
        "id": saved_at,
        "saved_at": saved_at,
        "settings": snapshot,
    }
    history.append(entry)
    atomic_write_json(path, history)
    return entry
