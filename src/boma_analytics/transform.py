"""Convert raw ingestion JSONL outputs into CSV files for modeling."""

from __future__ import annotations

import csv
import json
import logging
from argparse import ArgumentParser
from pathlib import Path
from typing import Iterable

import yaml

logger = logging.getLogger(__name__)


def read_jsonl(path: Path) -> Iterable[dict]:
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            yield json.loads(line)


def normalize_record(rec: dict) -> dict:
    out = {
        "listing_id": rec.get("listing_id"),
        "url": rec.get("url"),
        "title": rec.get("title"),
        "price_kes": rec.get("price_kes"),
        "price_text": rec.get("price_text"),
        "location": rec.get("location"),
        "bedrooms": rec.get("bedrooms"),
        "bathrooms": rec.get("bathrooms"),
        "area_sqm": rec.get("area_sqm"),
        "description_snippet": rec.get("description_snippet"),
        "photo_count": rec.get("photo_count"),
        # store lists / dicts as JSON strings so CSV remains simple
        "feature_badges": json.dumps(rec.get("feature_badges")) if rec.get("feature_badges") is not None else None,
        "source_page": rec.get("source_page"),
        "scraped_at": rec.get("scraped_at"),
        "detail": json.dumps(rec.get("detail"), ensure_ascii=False) if rec.get("detail") is not None else None,
    }
    return out


def process_run_dir(run_dir: Path, processed_base: Path) -> Path:
    listings_path = run_dir / "listings.jsonl"
    if not listings_path.exists():
        raise FileNotFoundError(f"Expected listings.jsonl in {run_dir}")

    processed_run_dir = processed_base / run_dir.name
    processed_run_dir.mkdir(parents=True, exist_ok=True)
    out_path = processed_run_dir / "listings.csv"

    records = list(read_jsonl(listings_path))
    if not records:
        logger.warning("No records found in %s", listings_path)

    normalized = [normalize_record(r) for r in records]

    fieldnames = [
        "listing_id",
        "url",
        "title",
        "price_kes",
        "price_text",
        "location",
        "bedrooms",
        "bathrooms",
        "area_sqm",
        "description_snippet",
        "photo_count",
        "feature_badges",
        "source_page",
        "scraped_at",
        "detail",
    ]

    with out_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in normalized:
            writer.writerow(row)

    logger.info("Wrote CSV to %s (%d rows)", out_path, len(normalized))
    return out_path


def main(argv: list[str] | None = None) -> None:
    parser = ArgumentParser(description="Convert raw ingestion JSONL runs to CSV")
    parser.add_argument("--run-dir", type=Path, help="Path to a single raw run directory to process")
    parser.add_argument("--all", action="store_true", help="Process all runs under the raw source directory")
    parser.add_argument("--output-dir", type=Path, help="Base processed output directory (overrides default)")
    args = parser.parse_args(argv)

    project_root = Path(__file__).resolve().parents[2]
    cfg_path = project_root / "config" / "config.yaml"
    with cfg_path.open("r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    source_name = cfg["output"]["source_name"]
    raw_base = project_root / cfg["output"]["raw_dir"] / source_name

    processed_base = args.output_dir or (project_root / "data" / "processed" / source_name)

    if args.run_dir:
        process_run_dir(args.run_dir, processed_base)
        return

    if args.all:
        if not raw_base.exists():
            raise FileNotFoundError(f"Raw base directory not found: {raw_base}")
        for child in sorted(raw_base.iterdir()):
            if child.is_dir():
                process_run_dir(child, processed_base)
        return

    parser.error("Either --run-dir or --all must be provided")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
