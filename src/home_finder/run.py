from __future__ import annotations

from . import user_cli
from .crawler_591_browser_v3 import Browser591Crawler


def main() -> None:
    user_cli.Browser591Crawler = Browser591Crawler
    user_cli.main()


if __name__ == "__main__":
    main()
