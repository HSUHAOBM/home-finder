from __future__ import annotations

import json

from flask import jsonify

from . import web_app_v13 as previous


app = previous.app
base = previous.base
_index_v13 = previous.index_v13
COMMUTE_SETTINGS_PATH = base.BASE_DIR / "data" / "commute_settings.json"


def index_v14():
    html = _index_v13()
    assets = (
        '<link rel="stylesheet" href="/static/dashboard_v14.css">'
        '<script src="/static/dashboard_v14.js" defer></script>'
    )
    return html.replace("</head>", assets + "</head>")


@app.get("/api/commute-settings")
def api_commute_settings_v14():
    if not COMMUTE_SETTINGS_PATH.exists():
        return jsonify({"destinations": []})
    try:
        payload = json.loads(COMMUTE_SETTINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return jsonify({"error": "通勤地點設定無法讀取"}), 500
    destinations = payload.get("destinations", []) if isinstance(payload, dict) else []
    return jsonify({"destinations": [item for item in destinations if isinstance(item, dict)]})


def activate() -> None:
    previous.activate()
    app.view_functions["index"] = index_v14


def main() -> None:
    activate()
    base.main()


if __name__ == "__main__":
    main()
