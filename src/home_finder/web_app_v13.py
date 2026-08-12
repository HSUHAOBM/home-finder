from __future__ import annotations

from flask import jsonify, request

from . import web_app_v8 as favorites_app
from . import web_app_v12 as previous


app = previous.app
base = previous.base
_index_v12 = previous.index_v12


def index_v13():
    html = _index_v12()
    assets = (
        '<link rel="stylesheet" href="/static/dashboard_v13.css">'
        '<script src="/static/dashboard_v13.js" defer></script>'
    )
    return html.replace("</head>", assets + "</head>")


@app.post("/api/favorites/note")
def api_favorite_note_v13():
    body = request.get_json(silent=True) or {}
    source = str(body.get("source") or "591").strip()
    external_id = str(body.get("id") or "").strip()
    note = str(body.get("note") or "").strip()
    if not external_id:
        return jsonify({"error": "缺少房源編號"}), 400
    if len(note) > 500:
        return jsonify({"error": "收藏備註最多 500 字"}), 400

    with favorites_app._favorites_lock:
        try:
            items = favorites_app._load_favorite_items()
        except (ValueError, OSError) as exc:
            return jsonify({"error": f"無法讀取收藏：{exc}"}), 500
        key = favorites_app._favorite_key(source, external_id)
        target = next(
            (
                item for item in items
                if favorites_app._favorite_key(item.get("source"), item.get("id")) == key
            ),
            None,
        )
        if target is None:
            return jsonify({"error": "找不到這筆收藏"}), 404
        if note:
            target["favorite_note"] = note
            target["favorite_note_updated_at"] = base._iso_now()
        else:
            target.pop("favorite_note", None)
            target.pop("favorite_note_updated_at", None)
        favorites_app._write_favorite_items(items)
        result = favorites_app._decorate_with_favorites(
            favorites_app._load_previous_dashboard_payload(),
            refresh_snapshots=False,
        )
    return jsonify(result)


def activate() -> None:
    previous.activate()
    app.view_functions["index"] = index_v13


def main() -> None:
    activate()
    base.main()


if __name__ == "__main__":
    main()
