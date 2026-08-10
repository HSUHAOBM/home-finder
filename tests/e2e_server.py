from __future__ import annotations

import argparse
import os
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from home_finder import web_app_v7, web_app_v11  # noqa: E402
from home_finder.result_store import write_result_records  # noqa: E402
from home_finder.storage import atomic_write_json  # noqa: E402
from home_finder.user_models import HomeListing  # noqa: E402


def _listing(
    external_id: str,
    title: str,
    profile: str,
    price: float,
    **changes: Any,
) -> HomeListing:
    values: dict[str, Any] = {
        "source": "E2E 測試資料",
        "external_id": external_id,
        "title": title,
        "url": f"https://example.com/{external_id}",
        "city": "高雄市",
        "district": "楠梓區",
        "total_price_wan": price,
        "property_type": "電梯大樓",
        "main_area_ping": 20,
        "rooms": 3,
        "baths": 2,
        "age_years": 5,
        "current_floor": 10,
        "total_floors": 15,
        "parking_type": "平面式",
        "has_parking": True,
        "search_profile": profile,
    }
    values.update(changes)
    return HomeListing(**values)


def _record(
    listing: HomeListing,
    profile: str,
    status: str,
    score: float,
    *,
    missing_required: list[str] | None = None,
    hard_failures: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "listing": listing.to_dict(),
        "profile": profile,
        "status": status,
        "score": score,
        "hard_failures": hard_failures or [],
        "missing_required": missing_required or [],
        "strengths": ["E2E 測試房源"],
        "concerns": [],
        "duplicate_ids": [],
    }


def _records() -> list[dict[str, Any]]:
    condo = _listing(
        "E2E-CONDO",
        "E2E 可接受大樓",
        "大樓公寓華廈",
        1150,
    )
    condo_without_parking = _listing(
        "E2E-NEAR",
        "E2E 跨分類搜尋房源",
        "大樓公寓華廈",
        698,
        parking_type="無",
        has_parking=False,
    )
    condo_mechanical_parking = _listing(
        "E2E-MECHANICAL",
        "E2E 機械車位房源",
        "大樓公寓華廈",
        758,
        parking_type="機械式",
        has_parking=True,
    )
    house = _listing(
        "E2E-HOUSE",
        "E2E 完全符合透天",
        "透天別墅",
        1000,
        property_type="透天厝",
        current_floor=1,
        total_floors=3,
        has_garden=True,
    )
    presale = _listing(
        "E2E-PRESALE",
        "E2E 待確認預售",
        "預售屋",
        0,
        deal_kind="預售屋",
        age_years=None,
        main_area_ping=None,
        parking_type=None,
        has_parking=None,
    )
    return [
        _record(condo, "大樓公寓華廈", "qualified", 88),
        _record(
            condo_without_parking,
            "大樓公寓華廈",
            "rejected",
            87,
            hard_failures=["詳情欄位顯示無汽車位"],
        ),
        _record(
            condo_mechanical_parking,
            "大樓公寓華廈",
            "rejected",
            87,
            hard_failures=["不是平面車位：機械式"],
        ),
        _record(house, "透天別墅", "qualified", 95),
        _record(
            presale,
            "預售屋",
            "needs_verification",
            60,
            missing_required=["主建物坪數待確認"],
        ),
    ]


@contextmanager
def isolated_app(data_dir: Path) -> Iterator[Any]:
    original_paths = (
        web_app_v7.base.RESULTS_PATH,
        web_app_v7.base.SUMMARY_PATH,
        web_app_v7.DIAGNOSTICS_PATH,
        web_app_v7.SEARCH_HISTORY_PATH,
        web_app_v7.SETTINGS_HISTORY_PATH,
    )
    web_app_v7.base.RESULTS_PATH = data_dir / "current-results.json"
    web_app_v7.base.SUMMARY_PATH = data_dir / "current-summary.md"
    web_app_v7.DIAGNOSTICS_PATH = data_dir / "diagnostics.json"
    web_app_v7.SEARCH_HISTORY_PATH = data_dir / "search-history.json"
    web_app_v7.SETTINGS_HISTORY_PATH = data_dir / "settings-history.json"
    try:
        write_result_records(web_app_v7.base.RESULTS_PATH, _records())
        atomic_write_json(
            web_app_v7.SEARCH_HISTORY_PATH,
            [
                {
                    "finished_at": "2026-08-09T01:02:03+00:00",
                    "profile": "大樓公寓華廈",
                    "mode": "daily",
                    "fetched": 1,
                    "duration_seconds": 125.4,
                    "district_count": 1,
                }
            ],
        )
        web_app_v11.activate()
        yield web_app_v11.app
    finally:
        (
            web_app_v7.base.RESULTS_PATH,
            web_app_v7.base.SUMMARY_PATH,
            web_app_v7.DIAGNOSTICS_PATH,
            web_app_v7.SEARCH_HISTORY_PATH,
            web_app_v7.SETTINGS_HISTORY_PATH,
        ) = original_paths


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    data_dir = (
        Path(tempfile.gettempdir()) / f"home-finder-e2e-server-{os.getpid()}"
    )
    data_dir.mkdir(exist_ok=False)
    try:
        with isolated_app(data_dir) as app:
            print(f"E2E server: http://127.0.0.1:{args.port}", flush=True)
            app.run(
                host="127.0.0.1",
                port=args.port,
                debug=False,
                use_reloader=False,
            )
    finally:
        for name in (
            "current-results.json",
            "current-summary.md",
            "diagnostics.json",
        ):
            (data_dir / name).unlink(missing_ok=True)
        data_dir.rmdir()


if __name__ == "__main__":
    main()
