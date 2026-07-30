"""
BuyRentKenya Multi-Category Parallel Scraper

Scrapes '/houses-for-sale' and '/flats-apartments-for-sale' concurrently
using Python multiprocessing, logs live color-coded progress, and streams
data into a single unified CSV file.
"""

from __future__ import annotations

import csv
import json
import logging
import multiprocessing
from boma_analytics.sources.buyrentkenya import BuyRentKenyaClient, BuyRentKenyaConfig
import sys


# ==============================================================================
# Terminal Color Codes & Formatter
# ==============================================================================
COLOR_GREEN = "\033[92m"
COLOR_CYAN = "\033[96m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"


class CategoryColorFormatter(logging.Formatter):
    """Custom formatter to inject category-specific ANSI colors into log streams."""

    def __init__(self, category_name: str, color_code: str):
        super().__init__()
        self.category_name = category_name
        self.color_code = color_code

    def format(self, record: logging.LogRecord) -> str:
        timestamp = self.formatTime(record, "%H:%M:%S")

        if record.levelno >= logging.ERROR:
            color = COLOR_RED
        elif record.levelno >= logging.WARNING:
            color = COLOR_YELLOW
        else:
            color = self.color_code

        header = f"{color}{COLOR_BOLD}[{self.category_name}]{COLOR_RESET}"
        return f"{timestamp} {header} {color}{record.getMessage()}{COLOR_RESET}"


def run_scraper_job(
    search_path: str,
    category_name: str,
    color_code: str,
    queue: multiprocessing.Queue,
    base_config: BuyRentKenyaConfig,
) -> None:
    """Worker process function for scraping a specific search category."""
    # Process-level logger setup
    logger = logging.getLogger(category_name)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(CategoryColorFormatter(category_name, color_code))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    config = BuyRentKenyaConfig(
        base_url=base_config.base_url,
        search_path=search_path,
        request_timeout=base_config.request_timeout,
        request_delay_seconds=base_config.request_delay_seconds,
        user_agent=base_config.user_agent,
        max_pages=base_config.max_pages,
    )

    client = BuyRentKenyaClient(config)
    logger.info("Starting scraper task for: %s", search_path)

    try:
        first_page = client.fetch_search_page(page=1)
        total_pages = client.get_total_pages(first_page)

        if config.max_pages:
            total_pages = min(total_pages, config.max_pages)

        logger.info("Found %d total pages to scrape", total_pages)

        total_scraped = 0
        for page_num in range(1, total_pages + 1):
            if page_num == 1:
                page_soup = first_page
            else:
                page_soup = client.fetch_search_page(page_num)

            cards = page_soup.select(".listing-card")
            page_count = 0

            for card in cards:
                item = client.extract_listing_features(card)

                if item.get("_scrape_error"):
                    logger.warning(
                        "Detail page warning for listing %s: %s",
                        item.get("listing_id"),
                        item.pop("_scrape_error"),
                    )

                if item.get("price"):
                    # Tag record source category
                    item["search_category"] = category_name

                    # Convert Python lists (amenities) to JSON strings for CSV compatibility
                    for k, v in item.items():
                        if isinstance(v, list):
                            item[k] = json.dumps(v)

                    queue.put(item)
                    total_scraped += 1
                    page_count += 1

            pct = (page_num / total_pages) * 100
            logger.info(
                "Progress: Page %d/%d (%.1f%% complete) | +%d listings (%d total scraped)",
                page_num,
                total_pages,
                pct,
                page_count,
                total_scraped,
            )

    except Exception as e:
        logger.error("Fatal exception in worker execution: %s",
                     e, exc_info=True)
    finally:
        queue.put("DONE")
        logger.info(
            "Completed scraping sequence. Total listings sent to writer: %d",
            total_scraped,
        )


# ==============================================================================
# Writer Job (CSV Sync)
# ==============================================================================
ALL_CSV_HEADERS = [
    "listing_id",
    "search_category",
    "price",
    "property_type",
    "bedrooms",
    "bathrooms",
    "size",
    "property_url",
    "description",
    "created_at",
    "county",
    "city",
    "area",
    "days_on_market",
    "seller_type",
    "internal_features",
    "external_features",
    "nearby",
]


def csv_writer_job(
    output_filepath: str, queue: multiprocessing.Queue, expected_workers: int
) -> None:
    """Dedicated process that consumes queued items and appends them to a CSV file."""
    logger = logging.getLogger("CSVWriter")
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(CategoryColorFormatter("CSV Writer", COLOR_YELLOW))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    logger.info("Initializing CSV stream writer -> %s", output_filepath)

    finished_workers = 0
    total_written = 0

    with open(
        output_filepath, "w", newline="", encoding="utf-8"
    ) as csvfile:
        writer = csv.DictWriter(
            csvfile, fieldnames=ALL_CSV_HEADERS, extrasaction="ignore"
        )
        writer.writeheader()
        csvfile.flush()

        while finished_workers < expected_workers:
            msg = queue.get()
            if msg == "DONE":
                finished_workers += 1
                logger.info(
                    "Worker process reported DONE (%d/%d completed)",
                    finished_workers,
                    expected_workers,
                )
                continue

            writer.writerow(msg)
            total_written += 1

            # Periodically flush to disk so file can be inspected while running
            if total_written % 10 == 0:
                csvfile.flush()

        csvfile.flush()

    logger.info(
        "CSV Writer finished. Total saved listings in '%s': %d",
        output_filepath,
        total_written,
    )


# ==============================================================================
# Main Execution Entry Point
# ==============================================================================
if __name__ == "__main__":
    # Change max_pages=None to scrape everything
    config = BuyRentKenyaConfig(max_pages=None)
    output_filename = "buyrentkenya_listings.csv"

    categories_to_scrape = [
        {
            "search_path": "/houses-for-sale",
            "category_name": "Houses",
            "color_code": COLOR_GREEN,
        },
        {
            "search_path": "/flats-apartments-for-sale",
            "category_name": "Apartments",
            "color_code": COLOR_CYAN,
        },
    ]

    communication_queue = multiprocessing.Queue()
    processes: list[multiprocessing.Process] = []

    # 1. Launch CSV Writer Process
    writer_process = multiprocessing.Process(
        target=csv_writer_job,
        args=(output_filename, communication_queue, len(categories_to_scrape)),
    )
    writer_process.start()
    processes.append(writer_process)

    # 2. Launch Scraper Worker Processes
    for cat in categories_to_scrape:
        p = multiprocessing.Process(
            target=run_scraper_job,
            args=(
                cat["search_path"],
                cat["category_name"],
                cat["color_code"],
                communication_queue,
                config,
            ),
        )
        p.start()
        processes.append(p)

    # 3. Wait for all processes to complete
    for p in processes:
        p.join()

    print(f"\n{COLOR_GREEN}{COLOR_BOLD}=== SCRAPE COMPLETE ==={COLOR_RESET}")
    print(f"Data saved to: {output_filename}\n")
