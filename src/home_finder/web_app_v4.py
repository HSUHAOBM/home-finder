from __future__ import annotations

import copy
import json
from datetime import datetime, timedelta, timezone

from flask import jsonify, render_template, request

from . import web_app as base
from . import web_app_v3 as previous
from .crawler_591_multi import MultiPage591ResaleCrawler
from .crawler_591_presale_multi import MultiDistrict591PresaleCrawler
from .listing_history import annotate_history
from .make_report import render_report
from .user_models import HomeListing
from .user_ranking_v5 import evaluate_all


DEFAULT_SETTINGS = copy.deepcopy(previous.DEFAULT_SETTINGS)
DEFAULT_SETTINGS["search"] = {
    "resale_details": 50,
    "presale_details": 30,
    "pages": 3,
    "publish_days": 3,
}
DEFAULT_SETTINGS["profiles"]["大樓公寓華廈"].update(
    {"require_high_floor": True, "min_floor_ratio": 2 / 3}
)


def load_settings() -> dict:
    config = json.loads(base.CONFIG_PATH.read_text(encoding="utf-8"))
    stored = config.get("editable_criteria")
    result = previous._merge(DEFAULT_SETTINGS, stored)
    if not isinstance(stored, dict) or "pages" not in stored.get("search", {}):
        result["search"] = copy.deepcopy(DEFAULT_SETTINGS["search"])
    return result


def validate_settings(raw: dict) -> dict:
    result = previous.validate_settings(raw)
    search = raw.get("search", {})
    result["search"]["pages"] = previous._integer(search.get("pages"), "每種中古屋頁數", 3, 10)
    publish_days = previous._integer(search.get("publish_days"), "刊登時間", 0, 30)
    if publish_days not in {0, 1, 3, 5, 7, 15, 30}:
        raise ValueError("刊登時間只能選擇不限、1、3、5、7、15 或 30 天")
    if result["search"]["presale_details"] > 30:
        raise ValueError("預售屋詳情上限不可超過 30")
    result["search"]["publish_days"] = publish_days
    condo = raw.get("profiles", {}).get("大樓公寓華廈", {})
    result["profiles"]["大樓公寓華廈"]["require_high_floor"] = bool(
        condo.get("require_high_floor")
    )
    result["profiles"]["大樓公寓華廈"]["min_floor_ratio"] = previous._number(
        condo.get("min_floor_ratio"), "最低樓層比例", 0.5, 1
    )
    return result


def save_settings(settings: dict) -> None:
    previous.save_settings(settings)
    config = json.loads(base.CONFIG_PATH.read_text(encoding="utf-8"))
    config["source"]["pages"] = settings["search"]["pages"]
    config["source"]["publish_days"] = settings["search"]["publish_days"]
    base.CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


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


def _filter_recent_presales(listings: list[HomeListing], publish_days: int) -> list[HomeListing]:
    if publish_days == 0:
        return listings
    cutoff = datetime.now(timezone.utc) - timedelta(days=publish_days)
    recent: list[HomeListing] = []
    for listing in listings:
        if listing.search_profile != "預售屋" or not listing.first_seen_at:
            recent.append(listing)
            continue
        try:
            if datetime.fromisoformat(listing.first_seen_at) >= cutoff:
                recent.append(listing)
        except ValueError:
            recent.append(listing)
    return recent


def _run_search() -> None:
    try:
        config = json.loads(base.CONFIG_PATH.read_text(encoding="utf-8"))
        settings = load_settings()
        source = config["source"]
        search = settings["search"]
        delay = max(2.0, float(source.get("delay_seconds", 2)))
        common = {
            "districts": settings["districts"],
            "max_pages": search["pages"],
            "publish_days": search["publish_days"],
            "max_details": search["resale_details"],
            "delay_seconds": delay,
            "headless": bool(source.get("headless", True)),
        }

        base._update_state(
            phase="condo",
            message=f"目標 01：正在讀取大樓／華廈，共 {search['pages']} 頁…",
        )
        condo = MultiPage591ResaleCrawler(profile="大樓公寓華廈", **common).fetch()
        base._update_state(
            phase="house",
            message=f"目標 02：正在讀取透天／車墅，共 {search['pages']} 頁…",
        )
        house = MultiPage591ResaleCrawler(profile="透天別墅", **common).fetch()
        base._update_state(
            phase="presale",
            message="目標 03：正在讀取四個行政區的預售屋列表…",
        )
        presale = MultiDistrict591PresaleCrawler(
            districts=settings["districts"],
            max_details=search["presale_details"],
            delay_seconds=delay,
            headless=bool(source.get("headless", True)),
        ).fetch()

        base._update_state(phase="history", message="正在標記新房源、更新與曾看過房源…")
        listings = annotate_history(
            condo + house + presale,
            path=base.BASE_DIR / "data" / "listing_history.json",
        )
        listings = _filter_recent_presales(listings, search["publish_days"])
        base._update_state(phase="ranking", message="正在依三套條件分別評分與去重…")
        records = [item.to_dict() for item in evaluate_all(listings, settings)]
        base.RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        base.RESULTS_PATH.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
        base.SUMMARY_PATH.write_text(render_report(records), encoding="utf-8")

        summary = base.build_dashboard_payload(records)["summary"]
        base._update_state(
            running=False,
            phase="complete",
            message=(
                f"完成：共 {summary['total']} 筆，{summary['qualified']} 筆符合、"
                f"{summary['needs_verification']} 筆待確認"
            ),
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


_original_card = base._card


def _card(record: dict) -> dict:
    card = _original_card(record)
    listing = record["listing"]
    card.update(
        search_profile=listing.get("search_profile"),
        listing_updated_text=listing.get("listing_updated_text"),
        first_seen_at=listing.get("first_seen_at"),
        last_seen_at=listing.get("last_seen_at"),
        lifecycle_status=listing.get("lifecycle_status"),
    )
    return card


app = base.app
base._run_search = _run_search
base._card = _card


def index_v4():
    html = render_template("dashboard_v3.html")
    html = html.replace(
        "</head>",
        '<link rel="stylesheet" href="/static/dashboard_v4.css">'
        '<script src="/static/dashboard_v4.js" defer></script></head>',
    )
    return html


def api_settings_get_v4():
    return jsonify(load_settings())


def api_settings_post_v4():
    if base._state_snapshot()["running"]:
        return jsonify({"error": "搜尋進行中，完成後才能調整條件"}), 409
    try:
        settings = validate_settings(request.get_json(silent=True) or {})
        save_settings(settings)
        re_evaluate_existing(settings)
        return jsonify({"settings": settings, "results": base.load_dashboard_payload()})
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        return jsonify({"error": str(exc)}), 400


app.view_functions["index"] = index_v4
app.view_functions["api_settings_get"] = api_settings_get_v4
app.view_functions["api_settings_post"] = api_settings_post_v4


def main() -> None:
    base.main()


if __name__ == "__main__":
    main()
