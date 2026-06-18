"""Run multiple ingestion jobs in parallel using multiprocessing.

This script starts one process per source (currently `buyrentkenya` and
`property24`) and forwards source-specific CLI options to each job.
"""

from __future__ import annotations

import argparse
import logging
import multiprocessing as mp
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _worker(source: str, opts: dict[str, Any]) -> None:
    """Worker process: import pipeline functions and execute the requested ingestion.

    Importing inside the worker avoids pickling large modules when spawning.
    """
    try:
        if source == "buyrentkenya":
            from boma_analytics.pipeline import run_buyrentkenya_ingestion

            logger.info("Starting BuyRentKenya job (listing_type=%s)...", opts.get("listing_type"))
            run_buyrentkenya_ingestion(
                config_path=opts.get("config_path"),
                max_pages=opts.get("max_pages"),
                fetch_details=opts.get("fetch_details"),
                output_dir=opts.get("output_dir"),
                listing_type=opts.get("listing_type"),
            )
        elif source == "property24":
            from boma_analytics.pipeline import run_property24_ingestion

            logger.info("Starting Property24 job...")
            run_property24_ingestion(
                config_path=opts.get("config_path"),
                max_pages=opts.get("max_pages"),
                fetch_details=opts.get("fetch_details"),
                output_dir=opts.get("output_dir"),
            )
        else:
            raise ValueError(f"Unsupported source: {source}")
    except Exception:
        logger.exception("Worker for %s failed", source)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Parallel ingestion runner")

    parser.add_argument("--config", dest="config_path", type=Path, default=None,
                        help="Path to config.yaml (default: config/config.yaml)")
    parser.add_argument("--output-dir", dest="output_dir", type=Path, default=None,
                        help="Override output directory for all jobs")

    # BuyRentKenya options
    parser.add_argument("--buyrent-max-pages", type=int, default=None,
                        help="Limit BuyRentKenya pages")
    parser.add_argument("--buyrent-no-details", action="store_true",
                        help="Skip BuyRentKenya detail pages")
    parser.add_argument("--buyrent-listing-type", choices=["houses", "apartments"], default="houses",
                        help="Which BuyRentKenya listing type to scrape")

    # Property24 options
    parser.add_argument("--prop24-max-pages", type=int, default=None,
                        help="Limit Property24 pages")
    parser.add_argument("--prop24-no-details", action="store_true",
                        help="Skip Property24 detail pages")

    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Enable debug logging for runner and workers")

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    # Build per-source options
    buy_opts = {
        "config_path": args.config_path,
        "max_pages": args.buyrent_max_pages,
        "fetch_details": not args.buyrent_no_details,
        "output_dir": args.output_dir,
        "listing_type": args.buyrent_listing_type,
    }

    prop_opts = {
        "config_path": args.config_path,
        "max_pages": args.prop24_max_pages,
        "fetch_details": not args.prop24_no_details,
        "output_dir": args.output_dir,
    }

    processes = []
    for source, opts in (("buyrentkenya", buy_opts), ("property24", prop_opts)):
        p = mp.Process(target=_worker, args=(source, opts), name=f"ingest-{source}")
        p.start()
        logger.info("Started process %s (pid=%s)", p.name, p.pid)
        processes.append(p)

    # Wait for all to finish
    for p in processes:
        p.join()
        logger.info("Process %s exited with code %s", p.name, p.exitcode)


if __name__ == "__main__":
    main()
