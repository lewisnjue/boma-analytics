import multiprocessing
import time
import logging
import queue
import threading
from typing import Any

from boma_analytics.db import get_collection, get_mongo_db
from boma_analytics.sources.buyrentkenya import BuyRentKenyaClient, BuyRentKenyaConfig
from boma_analytics.sources.property_pro import PropertyPro, PropertyProConfig
# from boma_analytics.sources.property24 import Property24Client, Property24Config

logging.basicConfig(
    level=logging.INFO,
    format='%(processName)s (%(threadName)s) - %(levelname)s - %(message)s'
)


def mongo_writer_worker(db_queue: queue.Queue, collection: Any, source_name: str) -> None:
    """Background thread worker that consumes items from the buffer queue 

    and writes them to MongoDB without blocking the main scraper.
    """
    while True:
        data = db_queue.get()
        if data is None:
            db_queue.task_done()
            break
        if isinstance(data, str):
            document = {"description": data, "scraped_at": time.time()}
            upsert_filter = {"description": data}
        else:
            document = dict(data)
            document["scraped_at"] = time.time()

            if "listing_id" in document and document["listing_id"]:
                upsert_filter = {"listing_id": document["listing_id"]}
            else:
                upsert_filter = {
                    "Title": document.get("Title"),
                    "Price (KSh)": document.get("Price (KSh)"),
                    "Location": document.get("Location")
                }

        try:
            collection.update_one(
                upsert_filter, {"$set": document}, upsert=True)
        except Exception as e:
            logging.error(f"Failed to write record to {source_name}: {e}")
        db_queue.task_done()


def run_job(scraper_class: Any) -> None:
    """Instantiates the scraper and streams data directly into an unblocking in-memory queue."""
    if scraper_class.__name__ == "BuyRentKenyaClient":
        scraper = scraper_class(BuyRentKenyaConfig())
        source_name = "buyrentkenya"
    elif scraper_class.__name__ == "Property24Client":
        scraper = scraper_class(Property24Config())
        source_name = "property24"
    else:
        scraper = scraper_class(PropertyProConfig())
        source_name = "property_pro"
    logging.info(f"Started scraping factory setup...")
    db = get_mongo_db()
    collection = get_collection(source_name, db=db)
    db_queue = queue.Queue(maxsize=200)
    writer_thread = threading.Thread(
        target=mongo_writer_worker,
        args=(db_queue, collection, source_name),
        name="DB-Writer",
        daemon=True  # Allows process to exit even if thread hangs
    )
    writer_thread.start()
    for index, data in enumerate(scraper.scrape_all(), start=1):
        db_queue.put(data)
        if index % 50 == 0:
            logging.info(f"Scraped and buffered {index} items...")
    logging.info(
        "Scraping loop completed. Waiting for buffer queue to flush to MongoDB...")
    db_queue.put(None)
    writer_thread.join()
    logging.info(f"All records cleanly written to database for {source_name}!")


if __name__ == "__main__":
    jobs = [PropertyPro, BuyRentKenyaClient]
    processes = []
    start_time = time.time()
    logging.info(
        "Initializing asynchronous decoupled multiprocessing pipeline...")

    for job_class in jobs:
        process_name = f"Process-{job_class.__name__}"
        p = multiprocessing.Process(
            target=run_job,
            args=(job_class,),
            name=process_name
        )
        processes.append(p)
        p.start()

    for p in processes:
        p.join()

    end_time = time.time()
    logging.info(f"All parallel scraping jobs completed in {
                 end_time - start_time:.2f} seconds.")
