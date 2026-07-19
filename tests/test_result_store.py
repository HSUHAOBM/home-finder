from __future__ import annotations

import pytest

from home_finder.result_store import (
    RANKING_VERSION,
    RESULT_SCHEMA_VERSION,
    decode_result_document,
    read_result_document,
    write_result_records,
)


def test_legacy_result_list_remains_readable():
    records = [{"listing": {"external_id": "A"}}]

    decoded, schema_version, ranking_version = decode_result_document(records)

    assert decoded == records
    assert schema_version is None
    assert ranking_version is None


def test_result_records_are_written_with_versions(tmp_path):
    path = tmp_path / "results.json"
    records = [{"listing": {"external_id": "A"}}]

    write_result_records(path, records)

    assert read_result_document(path) == (
        records,
        RESULT_SCHEMA_VERSION,
        RANKING_VERSION,
    )


def test_invalid_result_document_is_rejected():
    with pytest.raises(ValueError, match="結果檔格式不正確"):
        decode_result_document({"records": {}})
