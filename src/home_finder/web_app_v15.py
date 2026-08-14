from . import web_app_v14 as previous


app = previous.app
base = previous.base
_index_v14 = previous.index_v14


def index_v15():
    return _index_v14()


def activate() -> None:
    previous.activate()
    app.view_functions["index"] = index_v15


def main() -> None:
    activate()
    base.main()


if __name__ == "__main__":
    main()
