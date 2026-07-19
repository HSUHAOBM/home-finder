from __future__ import annotations

import copy
import json
from typing import Any

from flask import jsonify, render_template, request

from . import web_app as base
from .crawler_591_browser_v3 import Browser591Crawler
from .crawler_591_presale_v2 import Browser591PresaleCrawler
from .make_report import render_report
from .storage import atomic_write_json
from .user_models import HomeListing
from .user_ranking_v4 import evaluate_all


DEFAULT_SETTINGS = {
    "districts": ["楠梓區", "三民區", "橋頭區", "大社區"],
    "search": {"resale_details": 20, "presale_details": 12},
    "profiles": {
        "大樓公寓華廈": {
            "max_price": 1200,
            "target_price": 1100,
            "min_main_area": 15,
            "min_rooms": 2,
            "preferred_min_baths": 2,
            "preferred_max_age": 30,
            "require_flat_parking": True,
            "prefer_high_floor": True,
        },
        "透天別墅": {
            "max_price": 1200,
            "target_price": 1100,
            "preferred_max_age": 30,
            "require_parking": True,
            "prefer_garden": True,
        },
        "預售屋": {
            "max_price": 1200,
            "target_price": 1100,
            "min_main_area": 15,
            "min_rooms": 2,
            "preferred_min_baths": 2,
            "preferred_max_age": 5,
            "require_flat_parking": True,
        },
    },
}

ALLOWED_DISTRICTS = {"楠梓區", "三民區", "橋頭區", "大社區"}


def _merge(default: dict, stored: dict | None) -> dict:
    result = copy.deepcopy(default)
    if not isinstance(stored, dict):
        return result
    for key, value in stored.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        elif key in result:
            result[key] = value
    return result


def load_settings() -> dict:
    config = json.loads(base.CONFIG_PATH.read_text(encoding="utf-8"))
    return _merge(DEFAULT_SETTINGS, config.get("editable_criteria"))


def _number(value: Any, label: str, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label}必須是數字") from exc
    if not minimum <= number <= maximum:
        raise ValueError(f"{label}必須介於 {minimum:g} 至 {maximum:g}")
    return number


def _integer(value: Any, label: str, minimum: int, maximum: int) -> int:
    number = _number(value, label, minimum, maximum)
    if not number.is_integer():
        raise ValueError(f"{label}必須是整數")
    return int(number)


def validate_settings(raw: dict) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("設定格式不正確")
    districts = raw.get("districts")
    if not isinstance(districts, list) or not districts:
        raise ValueError("至少選擇一個行政區")
    if any(value not in ALLOWED_DISTRICTS for value in districts):
        raise ValueError("行政區設定不正確")

    profiles = raw.get("profiles", {})
    result = copy.deepcopy(DEFAULT_SETTINGS)
    result["districts"] = list(dict.fromkeys(districts))
    search = raw.get("search", {})
    result["search"] = {
        "resale_details": _integer(search.get("resale_details"), "中古屋讀取數", 1, 50),
        "presale_details": _integer(search.get("presale_details"), "預售屋讀取數", 1, 50),
    }

    for profile, defaults in DEFAULT_SETTINGS["profiles"].items():
        incoming = profiles.get(profile, {})
        target = result["profiles"][profile]
        target["max_price"] = _number(incoming.get("max_price"), f"{profile}總價上限", 300, 1200)
        target["target_price"] = _number(incoming.get("target_price"), f"{profile}目標總價", 300, 1200)
        if target["target_price"] > target["max_price"]:
            raise ValueError(f"{profile}目標總價不能高於總價上限")
        target["preferred_max_age"] = _number(
            incoming.get("preferred_max_age"), f"{profile}偏好屋齡", 0, 100
        )
        if "min_main_area" in defaults:
            target["min_main_area"] = _number(
                incoming.get("min_main_area"), f"{profile}最低主建物", 1, 100
            )
            target["min_rooms"] = _integer(incoming.get("min_rooms"), f"{profile}最低房數", 1, 10)
            target["preferred_min_baths"] = _integer(
                incoming.get("preferred_min_baths"), f"{profile}偏好衛浴", 1, 10
            )
            target["require_flat_parking"] = bool(incoming.get("require_flat_parking"))
        if profile == "大樓公寓華廈":
            target["prefer_high_floor"] = bool(incoming.get("prefer_high_floor"))
        if profile == "透天別墅":
            target["require_parking"] = bool(incoming.get("require_parking"))
            target["prefer_garden"] = bool(incoming.get("prefer_garden"))
    return result


def save_settings(settings: dict) -> None:
    config = json.loads(base.CONFIG_PATH.read_text(encoding="utf-8"))
    config["editable_criteria"] = settings
    config["source"]["districts"] = settings["districts"]
    config["source"]["max_details"] = settings["search"]["resale_details"]
    config["source"]["presale_max_details"] = settings["search"]["presale_details"]
    atomic_write_json(base.CONFIG_PATH, config)


def _unique_listings(records: list[dict]) -> list[HomeListing]:
    listings: dict[str, HomeListing] = {}
    for record in records:
        listing = record.get("listing", {})
        external_id = str(listing.get("external_id", ""))
        if external_id and external_id not in listings:
            listings[external_id] = HomeListing.from_dict(listing)
    return list(listings.values())


def re_evaluate_existing(settings: dict) -> None:
    if not base.RESULTS_PATH.exists():
        return
    existing = json.loads(base.RESULTS_PATH.read_text(encoding="utf-8"))
    records = [item.to_dict() for item in evaluate_all(_unique_listings(existing), settings)]
    base.RESULTS_PATH.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    base.SUMMARY_PATH.write_text(render_report(records), encoding="utf-8")


def _run_search() -> None:
    try:
        config = json.loads(base.CONFIG_PATH.read_text(encoding="utf-8"))
        settings = load_settings()
        source = config["source"]
        delay = max(2.0, float(source.get("delay_seconds", 2)))

        base._update_state(phase="resale", message="正在讀取 591 中古屋詳情…")
        resale = Browser591Crawler(
            districts=settings["districts"],
            max_details=settings["search"]["resale_details"],
            delay_seconds=delay,
            headless=bool(source.get("headless", True)),
        ).fetch()
        base._update_state(phase="presale", message="正在讀取 591 預售屋詳情…")
        presale = Browser591PresaleCrawler(
            districts=settings["districts"],
            max_details=settings["search"]["presale_details"],
            delay_seconds=delay,
            headless=bool(source.get("headless", True)),
        ).fetch()
        base._update_state(phase="ranking", message="正在依目前條件分類、排序與去重…")
        records = [item.to_dict() for item in evaluate_all(resale + presale, settings)]
        base.RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        base.RESULTS_PATH.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
        base.SUMMARY_PATH.write_text(render_report(records), encoding="utf-8")

        summary = base.build_dashboard_payload(records)["summary"]
        base._update_state(
            running=False,
            phase="complete",
            message=f"完成：{summary['qualified']} 筆符合、{summary['needs_verification']} 筆待確認",
            finished_at=base._iso_now(),
            error=None,
        )
    except Exception as exc:  # pragma: no cover - depends on live website
        base._update_state(
            running=False,
            phase="error",
            message="搜尋未完成，請稍後再試",
            finished_at=base._iso_now(),
            error=str(exc),
        )


app = base.app
base._run_search = _run_search


def index_v3():
    return render_template("dashboard_v3.html")


app.view_functions["index"] = index_v3


@app.get("/api/settings")
def api_settings_get():
    return jsonify(load_settings())


@app.post("/api/settings")
def api_settings_post():
    if base._state_snapshot()["running"]:
        return jsonify({"error": "搜尋進行中，完成後才能調整條件"}), 409
    try:
        settings = validate_settings(request.get_json(silent=True) or {})
        save_settings(settings)
        re_evaluate_existing(settings)
        return jsonify({"settings": settings, "results": base.load_dashboard_payload()})
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        return jsonify({"error": str(exc)}), 400


def main() -> None:
    base.main()


if __name__ == "__main__":
    main()
