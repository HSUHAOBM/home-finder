from __future__ import annotations

import json

from flask import jsonify, request

from . import web_app_v5 as listing_app
from . import web_app_v6 as result_app
from . import web_app_v7 as crawl_app
from . import web_app_v9 as previous
from .listing_history import annotate_history
from .user_ranking_v6 import evaluate_all


app = previous.app
base = previous.base
_index_v9 = previous.index_v9


def index_v10():
    html = _index_v9()
    assets = (
        '<link rel="stylesheet" href="/static/dashboard_v10.css">'
        '<script src="/static/dashboard_v10.js" defer></script>'
    )
    return html.replace("</head>", assets + "</head>")


@app.post("/api/listings/import")
def api_import_listing_v10():
    payload = request.get_json(silent=True) or {}
    profile = payload.get("profile")
    url = str(payload.get("url") or "").strip()
    if profile not in {"大樓公寓華廈", "透天別墅"}:
        return jsonify({"error": "網址查核目前支援 591 中古屋"}), 400
    with base._state_lock:
        if base._state["running"]:
            return jsonify({"error": "搜尋進行中，完成後才能查核網址"}), 409
        base._state.update(
            running=True,
            phase="crawling",
            active_profile=profile,
            search_mode="manual",
            message="正在直接查核 591 房源網址…",
            started_at=base._iso_now(),
            finished_at=None,
            error=None,
        )

    try:
        settings = crawl_app.load_settings()
        config = json.loads(base.CONFIG_PATH.read_text(encoding="utf-8"))
        source = config["source"]
        crawler = crawl_app.TimedResaleCrawler(
            profile=profile,
            districts=settings["districts"],
            max_pages=max(3, int(settings["search"]["pages"])),
            publish_days=int(settings["search"]["publish_days"]),
            max_details=1,
            collection_max_price=float(
                source.get("collection_max_price", 1300)
            ),
            delay_seconds=max(2.0, float(source.get("delay_seconds", 2))),
            headless=True,
        )
        imported = crawler.fetch_url(url)
        imported = annotate_history(
            [imported], path=crawl_app.HISTORY_PATH
        )[0]
        existing = listing_app._load_existing_listings()
        listings = result_app.merge_search_results(
            existing, [imported], profile, "daily"
        )
        records = [
            item.to_dict() for item in evaluate_all(listings, settings)
        ]
        result_app._write_results(records)
        base._update_state(
            running=False,
            phase="complete",
            active_profile=profile,
            search_mode="manual",
            message=f"已查核並加入房源 {imported.external_id}",
            finished_at=base._iso_now(),
            error=None,
        )
        return jsonify(
            {
                "listing_id": imported.external_id,
                "results": previous.previous.load_dashboard_payload(),
            }
        )
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        base._update_state(
            running=False,
            phase="error",
            active_profile=profile,
            search_mode="manual",
            message="房源網址查核未完成，原有結果已保留",
            finished_at=base._iso_now(),
            error=str(exc),
        )
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        app.logger.exception("Unexpected failure while importing listing")
        base._update_state(
            running=False,
            phase="error",
            active_profile=profile,
            search_mode="manual",
            message="房源網址查核未完成，原有結果已保留",
            finished_at=base._iso_now(),
            error=str(exc),
        )
        return jsonify({"error": f"查核失敗：{type(exc).__name__}"}), 500


def activate() -> None:
    previous.activate()
    app.view_functions["index"] = index_v10


def main() -> None:
    activate()
    base.main()


if __name__ == "__main__":
    main()
