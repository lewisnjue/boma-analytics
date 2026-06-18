"""Run ingestion jobs and save raw data directly into MongoDB."""

from __future__ import annotations

import argparse
import json
import logging
import multiprocessing as mp
from pathlib import Path
from typing import Any

from boma_analytics.db import save_listings

logger = logging.getLogger(__name__)


def _worker(source: str, opts: dict[str, Any]) -> None:
    try:
        if source == "buyrentkenya":
            from boma_analytics.pipeline import run_buyrentkenya_ingestion

            logger.info("Starting BuyRentKenya job (listing_type=%s)...", opts.get("listing_type"))
            run_dir = run_buyrentkenya_ingestion(
                config_path=opts.get("config_path"),
                max_pages=opts.get("max_pages"),
                fetch_details=opts.get("fetch_details"),
                output_dir=opts.get("output_dir"),
                listing_type=opts.get("listing_type"),
            )
        elif source == "property24":
            from boma_analytics.pipeline import run_property24_ingestion

            logger.info("Starting Property24 job...")
            run_dir = run_property24_ingestion(
                config_path=opts.get("config_path"),
                max_pages=opts.get("max_pages"),
                fetch_details=opts.get("fetch_details"),
                output_dir=opts.get("output_dir"),
            )
        else:
            raise ValueError(f"Unsupported source: {source}")

        listings_file = Path(run_dir) / "listings.jsonl"
        if listings_file.exists():
            listings = []
            with listings_file.open("r", encoding="utf-8") as handle:
                for line in handle:
                    listings.append(json.loads(line))
            saved_count = save_listings(source, listings)
            logger.info("Saved %s %s listings to MongoDB", saved_count, source)
        else:
            logger.warning("No listings file found at %s", listings_file)
    except Exception:
        logger.exception("Worker for %s failed", source)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Parallel ingestion runner with MongoDB storage")

    parser.add_argument("--config", dest="config_path", type=Path, default=None,
                        help="Path to config.yaml (default: config/config.yaml)")
    parser.add_argument("--output-dir", dest="output_dir", type=Path, default=None,
                        help="Override output directory for all jobs")

    parser.add_argument("--buyrent-max-pages", type=int, default=None,
                        help="Limit BuyRentKenya pages")
    parser.add_argument("--buyrent-no-details", action="store_true",
                        help="Skip BuyRentKenya detail pages")
    parser.add_argument("--buyrent-listing-type", choices=["houses", "apartments"], default="houses",
                        help="Which BuyRentKenya listing type to scrape")

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
        p = mp.Process(target=_worker, args=(source, opts), name=f"db-ingest-{source}")
        p.start()
        logger.info("Started process %s (pid=%s)", p.name, p.pid)
        processes.append(p)

    for p in processes:
        p.join()
        logger.info("Process %s exited with code %s", p.name, p.exitcode)


if __name__ == "__main__":
    main()
