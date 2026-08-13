from __future__ import annotations

import json
import zipfile

from flask import jsonify, request

from . import web_app_v15 as previous
from . import web_app_v8 as favorites_app
from .real_price import query_real_price


app = previous.app
base = previous.base
_index_v15 = previous.index_v15
REAL_PRICE_CACHE_DIR = base.BASE_DIR / "data" / "cache" / "real-price"


@app.post("/api/favorites/real-price")
def api_favorite_real_price_v16():
    payload = request.get_json(silent=True) or {}
    source = str(payload.get("source") or "").strip()
    external_id = str(payload.get("id") or "").strip()
    months = payload.get("months", 12)
    if not source or not external_id or months not in (6, 12, 60, 120):
        return jsonify({"error": "查詢條件不正確。"}), 400
    favorites = favorites_app.load_dashboard_payload().get("favorites", [])
    key = favorites_app._favorite_key(source, external_id)
    listing = next(
        (item for item in favorites if favorites_app._favorite_key(item.get("source"), item.get("id")) == key),
        None,
    )
    if listing is None:
        return jsonify({"error": "找不到這筆收藏房源。"}), 404
    if not listing.get("district") or not listing.get("address"):
        return jsonify({"error": "這筆收藏缺少行政區或地址，無法比對實價登錄。"}), 400
    try:
        return jsonify(query_real_price(listing, cache_dir=REAL_PRICE_CACHE_DIR, months=months))
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        return jsonify({"error": f"官方資料讀取失敗：{exc}"}), 502
    except Exception:
        app.logger.exception("Unexpected real-price lookup failure")
        return jsonify({"error": "實價登錄查詢失敗，請稍後再試。"}), 502


def index_v16():
    html = _index_v15()
    assets = (
        '<link rel="stylesheet" href="/static/dashboard_v16.css">'
        '<script src="/static/dashboard_v16.js" defer></script>'
    )
    return html.replace("</head>", assets + "</head>")


def activate() -> None:
    previous.activate()
    app.view_functions["index"] = index_v16


def main() -> None:
    activate()
    base.main()


if __name__ == "__main__":
    main()
