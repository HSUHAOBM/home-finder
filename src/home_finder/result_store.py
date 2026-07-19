from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .storage import atomic_write_json


RESULT_SCHEMA_VERSION = 1
RANKING_VERSION = 1


def make_result_document(records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "ranking_version": RANKING_VERSION,
        "records": records,
    }


def decode_result_document(
    payload: Any,
) -> tuple[list[dict[str, Any]], int | None, int | None]:
    """Read current result documents and the legacy bare-list format."""
    if isinstance(payload, list):
        return payload, None, None
    if (
        not isinstance(payload, dict)
        or not isinstance(payload.get("records"), list)
    ):
        raise ValueError("結果檔格式不正確")
    return (
        payload["records"],
        payload.get("schema_version"),
        payload.get("ranking_version"),
    )


def read_result_document(
    path: Path,
) -> tuple[list[dict[str, Any]], int | None, int | None]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return decode_result_document(payload)


def read_result_records(path: Path) -> list[dict[str, Any]]:
    records, _, _ = read_result_document(path)
    return records


def result_document_is_current(
    schema_version: int | None, ranking_version: int | None
) -> bool:
    return (
        schema_version == RESULT_SCHEMA_VERSION
        and ranking_version == RANKING_VERSION
    )


def write_result_records(path: Path, records: list[dict[str, Any]]) -> None:
    atomic_write_json(path, make_result_document(records))
