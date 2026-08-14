from __future__ import annotations

import json

from flask import jsonify, request

from . import web_app_v14 as previous
from .commute_estimator import estimate_commute


app = previous.app
base = previous.base
_index_v14 = previous.index_v14
COMMUTE_CACHE_PATH = base.BASE_DIR / "data" / "commute_cache.json"


def _destinations() -> list[dict[str, str]]:
    if not previous.COMMUTE_SETTINGS_PATH.exists():
        return []
    payload = json.loads(previous.COMMUTE_SETTINGS_PATH.read_text(encoding="utf-8"))
    return [item for item in payload.get("destinations", []) if item.get("name") and item.get("address")]


@app.post("/api/commute-estimate")
def api_commute_estimate_v15():
    payload = request.get_json(silent=True) or {}
    origin = str(payload.get("origin") or "").strip()
    origin_fallbacks = [
        str(value).strip() for value in (payload.get("origin_fallbacks") or [])
        if isinstance(value, str) and value.strip()
    ][:3]
    if not origin or len(origin) > 150:
        return jsonify({"error": "房源地址不完整，無法估算通勤"}), 400
    try:
        result = estimate_commute(
            origin, _destinations(), cache_path=COMMUTE_CACHE_PATH,
            origin_fallbacks=origin_fallbacks,
        )
        return jsonify(result)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception:
        app.logger.exception("Unexpected commute estimate failure")
        return jsonify({"error": "通勤估算服務暫時無法使用"}), 502


def index_v15():
    html = _index_v14()
    assets = (
        '<link rel="stylesheet" href="/static/dashboard_v15.css">'
        '<script src="/static/dashboard_v15.js" defer></script>'
    )
    return html.replace("</head>", assets + "</head>")


def activate() -> None:
    previous.activate()
    app.view_functions["index"] = index_v15


def main() -> None:
    activate()
    base.main()


if __name__ == "__main__":
    main()
