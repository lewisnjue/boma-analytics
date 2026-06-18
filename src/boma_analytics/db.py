"""MongoDB persistence utilities for Boma Analytics."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pymongo import MongoClient, UpdateOne
from pymongo.collection import Collection
from pymongo.database import Database


def load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def get_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_env_from_project_root() -> None:
    load_env_file(get_project_root() / ".env")


def get_mongo_uri() -> str:
    load_env_from_project_root()
    uri = (
        os.environ.get("MONGODB_URI")
        or os.environ.get("MONGODB_URL")
        or os.environ.get("DATABASE_URL")
    )
    if not uri:
        raise RuntimeError(
            "MongoDB URI is required. Set MONGODB_URI, MONGODB_URL, or DATABASE_URL in the environment or .env file."
        )
    return uri


def get_mongo_db() -> Database:
    uri = get_mongo_uri()
    client = MongoClient(uri)
    db_name = os.environ.get("MONGODB_DB", "boma_analytics")
    return client[db_name]


def get_collection(source_name: str, db: Database | None = None) -> Collection:
    db = db or get_mongo_db()
    collection_name = f"{source_name}_listings"
    return db[collection_name]


def save_listings(
    source_name: str,
    listings: list[dict[str, Any]],
    db: Database | None = None,
) -> int:
    collection = get_collection(source_name, db=db)
    operations = []
    for listing in listings:
        if not listing.get("listing_id"):
            continue
        doc = {**listing}
        doc["source"] = source_name
        operations.append(
            UpdateOne(
                {"source": source_name, "listing_id": doc["listing_id"]},
                {"$set": doc},
                upsert=True,
            )
        )
    if not operations:
        return 0
    result = collection.bulk_write(operations)
    return int(result.upserted_count + result.modified_count)
