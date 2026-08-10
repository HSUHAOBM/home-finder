from __future__ import annotations

from . import web_app_v10 as previous


app = previous.app
base = previous.base
_index_v10 = previous.index_v10


def index_v11():
    html = _index_v10()
    assets = (
        '<link rel="stylesheet" href="/static/dashboard_v11.css">'
        '<script src="/static/dashboard_v11.js" defer></script>'
    )
    return html.replace("</head>", assets + "</head>")


def activate() -> None:
    previous.activate()
    app.view_functions["index"] = index_v11


def main() -> None:
    activate()
    base.main()


if __name__ == "__main__":
    main()
