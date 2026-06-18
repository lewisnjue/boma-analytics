"""CLI entrypoint for boma-analytics."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from boma_analytics.pipeline import run_buyrentkenya_ingestion


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Boma Analytics data ingestion")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest = subparsers.add_parser(
        "ingest", help="Run data ingestion pipelines")
    ingest_sub = ingest.add_subparsers(dest="source", required=True)

    brk = ingest_sub.add_parser(
        "buyrentkenya", help="Scrape BuyRentKenya house listings")
    brk.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to config.yaml (default: config/config.yaml)",
    )
    brk.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Limit number of search result pages to scrape",
    )
    brk.add_argument(
        "--no-details",
        action="store_true",
        help="Skip fetching individual listing detail pages",
    )
    brk.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Override output directory for this run",
    )
    brk.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if getattr(
            args, "verbose", False) else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if args.command == "ingest" and args.source == "buyrentkenya":
        run_dir = run_buyrentkenya_ingestion(
            config_path=args.config,
            max_pages=args.max_pages,
            fetch_details=not args.no_details,
            output_dir=args.output_dir,
        )
        print(f"Ingestion complete. Raw data saved to: {run_dir}")


if __name__ == "__main__":
    main()
