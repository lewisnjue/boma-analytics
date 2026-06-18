"""Pipeline orchestration for data ingestion jobs."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from boma_analytics.ingestion import BuyRentKenyaClient, BuyRentKenyaConfig

logger = logging.getLogger(__name__)


def load_config(config_path: Path) -> dict[str, Any]:
    with config_path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def run_buyrentkenya_ingestion(
    config_path: Path | None = None,
    *,
    max_pages: int | None = None,
    fetch_details: bool | None = None,
    output_dir: Path | None = None,
) -> Path:
    project_root = Path(__file__).resolve().parents[2]
    config_path = config_path or project_root / "config" / "config.yaml"
    config = load_config(config_path)

    source_cfg = config["sources"]["buyrentkenya"]
    output_cfg = config["output"]

    scrape_config = BuyRentKenyaConfig(
        base_url=source_cfg["base_url"],
        search_path=source_cfg["search_path"],
        request_timeout=source_cfg["request_timeout"],
        request_delay_seconds=source_cfg["request_delay_seconds"],
        user_agent=source_cfg["user_agent"],
        max_pages=max_pages if max_pages is not None else source_cfg.get(
            "max_pages"),
        fetch_details=(
            fetch_details
            if fetch_details is not None
            else source_cfg.get("fetch_details", True)
        ),
    )

    client = BuyRentKenyaClient(scrape_config)
    listings = client.scrape_all()

    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    source_name = output_cfg["source_name"]
    raw_base = output_dir or project_root / output_cfg["raw_dir"] / source_name
    run_dir = raw_base / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)

    listings_path = run_dir / "listings.jsonl"
    with listings_path.open("w", encoding="utf-8") as handle:
        for listing in listings:
            handle.write(json.dumps(listing.to_dict(),
                         ensure_ascii=False) + "\n")

    metadata = {
        "source": source_name,
        "search_url": client.search_url,
        "scraped_at": datetime.now(UTC).isoformat(),
        "listing_count": len(listings),
        "max_pages": scrape_config.max_pages,
        "fetch_details": scrape_config.fetch_details,
        "output_file": str(listings_path.relative_to(project_root)),
    }
    metadata_path = run_dir / "metadata.json"
    metadata_path.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    logger.info("Saved %s listings to %s", len(listings), listings_path)
    return run_dir
