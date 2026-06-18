"""Pipeline orchestration for data ingestion jobs."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from boma_analytics.sources.buyrentkenya import BuyRentKenyaClient, BuyRentKenyaConfig
from boma_analytics.sources.property24 import Property24Client, Property24Config

logger = logging.getLogger(__name__)


def load_config(config_path: Path) -> dict[str, Any]:
    with config_path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _run_source_ingestion(
    source_name: str,
    client: Any,
    config: dict[str, Any],
    output_cfg: dict[str, Any],
    config_path: Path | None = None,
    *,
    max_pages: int | None = None,
    fetch_details: bool | None = None,
    output_dir: Path | None = None,
) -> Path:
    project_root = Path(__file__).resolve().parents[2]
    source_cfg = config["sources"][source_name]

    if hasattr(client, "config"):
        scrape_config = client.config
    else:
        scrape_config = None

    if scrape_config is None:
        raise ValueError("Client must expose a config attribute for ingestion")

    if max_pages is not None:
        scrape_config.max_pages = max_pages
    elif source_cfg.get("max_pages") is not None:
        scrape_config.max_pages = source_cfg.get("max_pages")

    if fetch_details is not None:
        scrape_config.fetch_details = fetch_details
    elif source_cfg.get("fetch_details") is not None:
        scrape_config.fetch_details = source_cfg.get("fetch_details")

    listings = client.scrape_all()

    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    raw_base = output_dir or Path(__file__).resolve().parents[2] / output_cfg["raw_dir"] / source_name
    run_dir = raw_base / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)

    listings_path = run_dir / "listings.jsonl"
    with listings_path.open("w", encoding="utf-8") as handle:
        for listing in listings:
            handle.write(json.dumps(listing.to_dict(), ensure_ascii=False) + "\n")

    metadata = {
        "source": source_name,
        "search_url": client.search_url,
        "scraped_at": datetime.now(UTC).isoformat(),
        "listing_count": len(listings),
        "max_pages": scrape_config.max_pages,
        "fetch_details": scrape_config.fetch_details,
        "output_file": str(listings_path.relative_to(Path(__file__).resolve().parents[2])),
    }
    metadata_path = run_dir / "metadata.json"
    metadata_path.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    logger.info("Saved %s listings to %s", len(listings), listings_path)
    return run_dir


def run_buyrentkenya_ingestion(
    config_path: Path | None = None,
    *,
    max_pages: int | None = None,
    fetch_details: bool | None = None,
    output_dir: Path | None = None,
    listing_type: str | None = None,
) -> Path:
    project_root = Path(__file__).resolve().parents[2]
    config_path = config_path or project_root / "config" / "config.yaml"
    config = load_config(config_path)
    output_cfg = config["output"]

    source_cfg = config["sources"]["buyrentkenya"]

    lt = (listing_type or "houses").lower()
    if lt not in {"houses", "apartments"}:
        raise ValueError("listing_type must be 'houses' or 'apartments'")

    if lt == "houses":
        search_path = source_cfg.get("search_path")
    else:
        # fallback to main search_path if apartments path not configured
        search_path = source_cfg.get("apartments_search_path", source_cfg.get("search_path"))

    scrape_config = BuyRentKenyaConfig(
        base_url=source_cfg["base_url"],
        search_path=search_path,
        request_timeout=source_cfg["request_timeout"],
        request_delay_seconds=source_cfg["request_delay_seconds"],
        user_agent=source_cfg["user_agent"],
        max_pages=source_cfg.get("max_pages"),
        fetch_details=source_cfg.get("fetch_details", True),
    )

    client = BuyRentKenyaClient(scrape_config)
    # store the listing type in output structure by creating a subfolder
    run_dir = _run_source_ingestion(
        source_name="buyrentkenya",
        client=client,
        config=config,
        output_cfg=output_cfg,
        config_path=config_path,
        max_pages=max_pages,
        fetch_details=fetch_details,
        output_dir=output_dir,
    )

    # Move run_dir under a listing_type subfolder if not already
    project_root = Path(__file__).resolve().parents[2]
    base_raw = output_dir or project_root / output_cfg["raw_dir"] / "buyrentkenya"
    typed_base = base_raw / lt
    typed_dir = typed_base / run_dir.name
    if not typed_dir.exists():
        typed_base.mkdir(parents=True, exist_ok=True)
        run_dir.rename(typed_dir)
    return typed_dir


def run_property24_ingestion(
    config_path: Path | None = None,
    *,
    max_pages: int | None = None,
    fetch_details: bool | None = None,
    output_dir: Path | None = None,
) -> Path:
    project_root = Path(__file__).resolve().parents[2]
    config_path = config_path or project_root / "config" / "config.yaml"
    config = load_config(config_path)
    output_cfg = config["output"]

    source_cfg = config["sources"]["property24"]
    scrape_config = Property24Config(
        base_url=source_cfg["base_url"],
        search_path=source_cfg["search_path"],
        request_timeout=source_cfg["request_timeout"],
        request_delay_seconds=source_cfg["request_delay_seconds"],
        user_agent=source_cfg["user_agent"],
        max_pages=source_cfg.get("max_pages"),
        fetch_details=source_cfg.get("fetch_details", True),
    )

    client = Property24Client(scrape_config)
    return _run_source_ingestion(
        source_name="property24",
        client=client,
        config=config,
        output_cfg=output_cfg,
        config_path=config_path,
        max_pages=max_pages,
        fetch_details=fetch_details,
        output_dir=output_dir,
    )
