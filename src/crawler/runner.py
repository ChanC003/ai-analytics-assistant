"""Crawler entrypoints — one-shot and continuous loop.

Run a single crawl:        python -m src.crawler.runner --once
Run the polling loop:      python -m src.crawler.runner --loop --interval 60

The Streamlit UI calls `crawl_once()` for its "Crawl now" button; the loop is
for leaving a terminal collecting history in the background.
"""

from __future__ import annotations

import argparse
import time
from dataclasses import dataclass
from datetime import datetime

from src.crawler.coingecko import CoinGeckoError, fetch_markets
from src.crawler.store import save_markets


@dataclass
class CrawlResult:
    ticks: int
    at: datetime
    error: str | None = None


def crawl_once(per_page: int = 50) -> CrawlResult:
    """Fetch one snapshot and persist it. Never raises — errors are returned."""
    try:
        rows = fetch_markets(per_page=per_page)
        n = save_markets(rows)
        return CrawlResult(ticks=n, at=datetime.now())
    except CoinGeckoError as exc:
        return CrawlResult(ticks=0, at=datetime.now(), error=str(exc))
    except Exception as exc:  # noqa: BLE001 — keep a long-running loop alive
        return CrawlResult(ticks=0, at=datetime.now(), error=f"{type(exc).__name__}: {exc}")


def run_loop(interval: int = 60, per_page: int = 50) -> None:
    print(f"Crawling CoinGecko every {interval}s (Ctrl+C to stop)...")
    while True:
        res = crawl_once(per_page=per_page)
        stamp = res.at.strftime("%H:%M:%S")
        if res.error:
            print(f"[{stamp}] ERROR: {res.error}")
        else:
            print(f"[{stamp}] saved {res.ticks} ticks")
        time.sleep(interval)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CoinGecko crawler.")
    parser.add_argument("--once", action="store_true", help="Single crawl then exit.")
    parser.add_argument("--loop", action="store_true", help="Poll continuously.")
    parser.add_argument("--interval", type=int, default=60, help="Loop interval (seconds).")
    parser.add_argument("--per-page", type=int, default=50, help="Number of top coins.")
    args = parser.parse_args()

    if args.loop:
        run_loop(interval=args.interval, per_page=args.per_page)
    else:  # default to a single crawl
        r = crawl_once(per_page=args.per_page)
        print(f"ERROR: {r.error}" if r.error else f"Saved {r.ticks} ticks at {r.at:%H:%M:%S}")
