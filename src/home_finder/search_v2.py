from __future__ import annotations

from . import search
from .crawler_591_presale_v2 import Browser591PresaleCrawler


def main() -> None:
    search.Browser591PresaleCrawler = Browser591PresaleCrawler
    search.main()


if __name__ == "__main__":
    main()
