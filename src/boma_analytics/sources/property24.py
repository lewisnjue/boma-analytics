"""Property24 source-specific ingestion logic."""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "Accept-Language": "en-US,en;q=0.9",
}


@dataclass
class Property24Config:
    base_url: str = "https://www.property24.co.ke"
    search_path: str = "/property-for-sale"
    request_timeout: int = 15
    request_delay_seconds: float = 1.0
    user_agent: str = (
        "Mozilla/5.0 (X11; Ubuntu; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    max_pages: int | None = None
    fetch_details: bool = True


@dataclass
class Property24ListingRecord:
    listing_id: str
    url: str
    title: str | None = None
    price_kes: int | None = None
    price_text: str | None = None
    location: str | None = None
    address: str | None = None
    bedrooms: int | None = None
    bathrooms: int | None = None
    area_sqm: float | None = None
    description_snippet: str | None = None
    photo_count: int | None = None
    feature_badges: list[str] = field(default_factory=list)
    source_page: int | None = None
    scraped_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat())
    detail: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class Property24Client:
    def __init__(self, config: Property24Config) -> None:
        self.config = config
        self.session = requests.Session()
        self.session.headers.update(
            {
                **DEFAULT_HEADERS,
                "User-Agent": config.user_agent,
            }
        )

    @property
    def search_url(self) -> str:
        return urljoin(self.config.base_url, self.config.search_path)

    def _get(self, url: str) -> requests.Response:
        response = self.session.get(url, timeout=self.config.request_timeout)
        response.raise_for_status()
        return response

    def _sleep(self) -> None:
        if self.config.request_delay_seconds > 0:
            time.sleep(self.config.request_delay_seconds)

    def fetch_search_page(self, page: int = 1) -> BeautifulSoup:
        url = self.search_url if page <= 1 else f"{self.search_url}?Page={page}"
        logger.info("Fetching Property24 search page %s: %s", page, url)
        response = self._get(url)
        return BeautifulSoup(response.text, "html.parser")

    def get_total_pages(self, soup: BeautifulSoup) -> int:
        pager = soup.select_one(".pagination")
        if not pager:
            return 1

        page_numbers: list[int] = []
        for link in pager.find_all("a", href=True):
            match = re.search(r"[?&]Page=(\d+)", link["href"])
            if match:
                page_numbers.append(int(match.group(1)))
                continue
            text = link.get_text(strip=True)
            if text.isdigit():
                page_numbers.append(int(text))

        return max(page_numbers) if page_numbers else 1

    def fetch_listing_detail(self, url: str) -> dict[str, Any]:
        logger.debug("Fetching Property24 detail page: %s", url)
        response = self._get(url)
        soup = BeautifulSoup(response.text, "html.parser")
        return parse_property24_detail(soup)

    def scrape_all(self) -> list[Property24ListingRecord]:
        first_page = self.fetch_search_page(page=1)
        total_pages = self.get_total_pages(first_page)
        if self.config.max_pages is not None:
            total_pages = min(total_pages, self.config.max_pages)

        logger.info("Scraping %s Property24 search page(s)", total_pages)
        listings: list[Property24ListingRecord] = []
        seen_ids: set[str] = set()

        for page in range(1, total_pages + 1):
            soup = first_page if page == 1 else self.fetch_search_page(page=page)
            cards = soup.select("div.p24_regularTile[itemtype='http://schema.org/Product']")
            logger.info("Page %s: found %s Property24 listing cards", page, len(cards))

            for card in cards:
                record = parse_property24_listing_card(card, source_page=page)
                if record.listing_id in seen_ids:
                    continue
                seen_ids.add(record.listing_id)

                if self.config.fetch_details:
                    self._sleep()
                    try:
                        record.detail = self.fetch_listing_detail(record.url)
                    except requests.RequestException as exc:
                        logger.warning(
                            "Failed to fetch Property24 detail for listing %s: %s",
                            record.listing_id,
                            exc,
                        )
                        record.detail = {"error": str(exc)}

                listings.append(record)

            if page < total_pages:
                self._sleep()

        logger.info("Scraped %s unique Property24 listings", len(listings))
        return listings


def parse_price_kes(price_text: str | None) -> int | None:
    if not price_text:
        return None
    digits = re.sub(r"[^\d]", "", price_text)
    return int(digits) if digits else None


def parse_area_sqm(text: str | None) -> float | None:
    if not text:
        return None
    normalized = text.replace(".", "").replace(",", ".")
    match = re.search(r"([\d.]+)\s*m", normalized, re.I)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def parse_property24_listing_card(card: Tag, source_page: int) -> Property24ListingRecord:
    listing_id = card.get("data-listing-number")
    if not listing_id:
        raise ValueError("Property24 card is missing data-listing-number")

    link = card.select_one("a[href][itemprop='url']") or card.select_one("link[itemprop='url']")
    href = None
    if link:
        href = link.get("href")
    if not href:
        raise ValueError("Property24 listing card is missing a listing URL")

    url = urljoin("https://www.property24.co.ke", href)
    title_el = card.select_one("meta[itemprop='name']")
    title = title_el["content"].strip() if title_el and title_el.get("content") else None

    price_el = card.select_one(".p24_price")
    price_text = price_el.get_text(strip=True) if price_el else None

    location_el = card.select_one(".p24_location")
    location = location_el.get_text(strip=True) if location_el else None

    address_el = card.select_one(".p24_address")
    address = address_el.get_text(strip=True) if address_el else None

    description_el = card.select_one(".p24_excerpt")
    description_snippet = description_el.get_text(strip=True) if description_el else None

    bedrooms = bathrooms = None
    area_sqm = None
    feature_badges: list[str] = []
    for feature in card.select(".p24_featureDetails, .p24_size"):
        label = feature.get("title") or feature.get_text(strip=True)
        value_el = feature.select_one("span")
        value = value_el.get_text(strip=True) if value_el else None
        if not label or not value:
            continue
        if "Bedrooms" in label:
            bedrooms = int(value) if value.isdigit() else None
            feature_badges.append(f"{value} Bedrooms")
        elif "Bathrooms" in label:
            bathrooms = int(value) if value.isdigit() else None
            feature_badges.append(f"{value} Bathrooms")
        elif "Floor Size" in label or "m²" in value or "m" in value:
            area_sqm = parse_area_sqm(value)
            feature_badges.append(value)
        else:
            feature_badges.append(value)

    return Property24ListingRecord(
        listing_id=listing_id,
        url=url,
        title=title,
        price_kes=parse_price_kes(price_text),
        price_text=price_text,
        location=location,
        address=address,
        bedrooms=bedrooms,
        bathrooms=bathrooms,
        area_sqm=area_sqm,
        description_snippet=description_snippet,
        photo_count=None,
        feature_badges=feature_badges,
        source_page=source_page,
    )


def parse_property24_detail(soup: BeautifulSoup) -> dict[str, Any]:
    detail: dict[str, Any] = {
        "title": soup.find("h1").get_text(strip=True) if soup.find("h1") else None,
        "price_text": None,
        "price_kes": None,
        "location": None,
        "address": None,
        "description": None,
        "json_ld": {},
    }

    json_ld = _extract_json_ld(soup)
    product = None
    if isinstance(json_ld, dict) and json_ld.get("@type") == "Product":
        product = json_ld
    elif isinstance(json_ld, list):
        for item in json_ld:
            if isinstance(item, dict) and item.get("@type") == "Product":
                product = item
                break

    if product is None:
        return detail

    offer = product.get("offers") or {}
    detail["price_text"] = offer.get("price") or product.get("offers", {}).get("price")
    detail["price_kes"] = parse_price_kes(detail["price_text"])
    detail["description"] = product.get("description")
    detail["json_ld"] = product

    return detail


def _extract_json_ld(soup: BeautifulSoup) -> Any:
    scripts = soup.find_all("script", type="application/ld+json")
    for script in scripts:
        if not script.string:
            continue
        text = script.string.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            continue
    return {}
