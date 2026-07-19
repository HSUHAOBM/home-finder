from __future__ import annotations

from . import search
from .crawler_591_presale_v2 import Browser591PresaleCrawler
from .user_ranking_v3 import evaluate_all


def main() -> None:
    search.Browser591PresaleCrawler = Browser591PresaleCrawler
    search.evaluate_all = evaluate_all
    search.main()


if __name__ == "__main__":
    main()
