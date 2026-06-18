"""Fetch and parse house listings from BuyRentKenya."""

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
class BuyRentKenyaConfig:
    base_url: str = "https://www.buyrentkenya.com"
    search_path: str = "/houses-for-sale"
    request_timeout: int = 15
    request_delay_seconds: float = 1.0
    user_agent: str = (
        "Mozilla/5.0 (X11; Ubuntu; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    max_pages: int | None = None
    fetch_details: bool = True


@dataclass
class ListingRecord:
    listing_id: str
    url: str
    title: str | None = None
    price_kes: int | None = None
    price_text: str | None = None
    location: str | None = None
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


class BuyRentKenyaClient:
    def __init__(self, config: BuyRentKenyaConfig) -> None:
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
        url = self.search_url if page <= 1 else f"{
            self.search_url}?page={page}"
        logger.info("Fetching search page %s: %s", page, url)
        response = self._get(url)
        return BeautifulSoup(response.text, "html.parser")

    def get_total_pages(self, soup: BeautifulSoup) -> int:
        nav = soup.select_one(".pagination-page-nav")
        if not nav:
            return 1

        page_numbers: list[int] = []
        for link in nav.find_all("a", href=True):
            match = re.search(r"[?&]page=(\d+)", link["href"])
            if match:
                page_numbers.append(int(match.group(1)))

        for item in nav.select(".page-item"):
            text = item.get_text(strip=True)
            if text.isdigit():
                page_numbers.append(int(text))

        return max(page_numbers) if page_numbers else 1

    def fetch_listing_detail(self, url: str) -> dict[str, Any]:
        logger.debug("Fetching detail page: %s", url)
        response = self._get(url)
        soup = BeautifulSoup(response.text, "html.parser")
        return parse_detail_page(soup)

    def scrape_all(self) -> list[ListingRecord]:
        first_page = self.fetch_search_page(page=1)
        total_pages = self.get_total_pages(first_page)
        if self.config.max_pages is not None:
            total_pages = min(total_pages, self.config.max_pages)

        logger.info("Scraping %s search page(s)", total_pages)
        listings: list[ListingRecord] = []
        seen_ids: set[str] = set()

        for page in range(1, total_pages + 1):
            soup = first_page if page == 1 else self.fetch_search_page(
                page=page)
            cards = soup.select(".listing-card")
            logger.info("Page %s: found %s listing cards", page, len(cards))

            for card in cards:
                record = parse_listing_card(card, source_page=page)
                if record.listing_id in seen_ids:
                    continue
                seen_ids.add(record.listing_id)

                if self.config.fetch_details:
                    self._sleep()
                    try:
                        record.detail = self.fetch_listing_detail(record.url)
                    except requests.RequestException as exc:
                        logger.warning(
                            "Failed to fetch detail for listing %s: %s",
                            record.listing_id,
                            exc,
                        )
                        record.detail = {"error": str(exc)}

                listings.append(record)

            if page < total_pages:
                self._sleep()

        logger.info("Scraped %s unique listings", len(listings))
        return listings


def parse_price_kes(price_text: str | None) -> int | None:
    if not price_text:
        return None
    digits = re.sub(r"[^\d]", "", price_text)
    return int(digits) if digits else None


def parse_count_from_badge(text: str) -> int | None:
    match = re.match(r"(\d+)\s+", text.strip())
    return int(match.group(1)) if match else None


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


def parse_listing_card(card: Tag, source_page: int) -> ListingRecord:
    link = card.select_one("a[href*='/listings/']")
    if not link or not link.get("href"):
        raise ValueError("Listing card is missing a listing URL")

    href = link["href"]
    listing_id = href.rstrip("/").split("-")[-1]
    url = urljoin("https://www.buyrentkenya.com", href)

    title_el = card.select_one(
        "span.text-title") or card.select_one("h2") or link
    title = title_el.get_text(strip=True) if title_el else None

    price_el = card.select_one("p.text-title.text-xl") or card.find(
        string=re.compile(r"KSh\s*[\d,]+")
    )
    price_text = (
        price_el.get_text(strip=True)
        if isinstance(price_el, Tag)
        else str(price_el).strip() if price_el else None
    )

    location_el = card.select_one("p.w-full.truncate")
    location = location_el.get_text(strip=True) if location_el else None

    description_el = card.select_one("h3.block.flex-1") or card.select_one(
        "h3.text-md.mb-3.hidden"
    )
    description_snippet = (
        description_el.get_text(strip=True) if description_el else None
    )

    photo_count_el = card.select_one("span.align-right.text-xs.font-semibold")
    photo_count = (
        int(photo_count_el.get_text(strip=True))
        if photo_count_el and photo_count_el.get_text(strip=True).isdigit()
        else None
    )

    feature_badges = [
        badge.get_text(strip=True)
        for badge in card.select(".swiper-slide span.whitespace-nowrap")
        if badge.get_text(strip=True)
    ]

    bedrooms = bathrooms = None
    area_sqm = None
    for badge in feature_badges:
        lower = badge.lower()
        if "bedroom" in lower:
            bedrooms = parse_count_from_badge(badge)
        elif "bathroom" in lower:
            bathrooms = parse_count_from_badge(badge)
        elif "m" in lower:
            area_sqm = parse_area_sqm(badge)

    return ListingRecord(
        listing_id=listing_id,
        url=url,
        title=title,
        price_kes=parse_price_kes(price_text),
        price_text=price_text,
        location=location,
        bedrooms=bedrooms,
        bathrooms=bathrooms,
        area_sqm=area_sqm,
        description_snippet=description_snippet,
        photo_count=photo_count,
        feature_badges=feature_badges,
        source_page=source_page,
    )


def _graph_index(graph: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for item in graph:
        item_id = item.get("@id")
        if item_id:
            indexed[item_id] = item
        item_type = item.get("@type")
        if item_type and item_id is None:
            indexed[str(item_type)] = item
    return indexed


def _resolve_ref(value: Any, index: dict[str, dict[str, Any]]) -> Any:
    if isinstance(value, dict) and "@id" in value:
        referenced = index.get(value["@id"])
        return referenced if referenced is not None else value
    return value


def _extract_images(product: dict[str, Any], index: dict[str, dict[str, Any]]) -> list[str]:
    images: list[str] = []
    for image in product.get("image", []):
        if isinstance(image, str):
            images.append(image)
        elif isinstance(image, dict):
            url = image.get("url") or image.get("@id")
            if url:
                images.append(url)
        elif isinstance(image, dict) and "@id" in image:
            resolved = index.get(image["@id"])
            if resolved:
                url = resolved.get("url") or resolved.get("@id")
                if url:
                    images.append(url)
    return images


def _extract_feature_section(soup: BeautifulSoup, heading_text: str) -> list[str]:
    heading = soup.find(
        lambda tag: tag.name in {"h2", "h3", "h4", "strong", "span"}
        and tag.get_text(strip=True).lower() == heading_text.lower()
    )
    if not heading:
        return []

    container = heading.find_parent(["section", "div"])
    if not container:
        return []

    features: list[str] = []
    for item in container.find_all(["li", "span", "p"]):
        text = item.get_text(strip=True)
        if not text or text.lower() == heading_text.lower():
            continue
        if len(text) > 60:
            continue
        if text not in features:
            features.append(text)
    return features


def _extract_house_features(soup: BeautifulSoup) -> dict[str, Any]:
    features: dict[str, Any] = {}
    heading = soup.find(
        lambda tag: tag.name in {"h2", "h3", "h4", "strong", "span"}
        and tag.get_text(strip=True).lower() == "house features"
    )
    if not heading:
        return features

    container = heading.find_parent(["section", "div"])
    if not container:
        return features

    text = container.get_text("\n", strip=True)
    patterns = {
        "created_at": r"Created At:\s*(.+)",
        "bedrooms": r"Bedrooms:\s*(\d+)",
        "bathrooms": r"Bathrooms:\s*(\d+)",
        "size": r"Size:\s*(.+)",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, text, re.I)
        if match:
            value: str | int = match.group(1).strip()
            if key in {"bedrooms", "bathrooms"}:
                value = int(value)
            features[key] = value
    return features


def parse_detail_page(soup: BeautifulSoup) -> dict[str, Any]:
    detail: dict[str, Any] = {
        "title": soup.find("h1").get_text(strip=True) if soup.find("h1") else None,
        "internal_features": _extract_feature_section(soup, "Internal features"),
        "external_features": _extract_feature_section(soup, "External features"),
        "house_features": _extract_house_features(soup),
    }

    script = soup.find("script", type="application/ld+json")
    if not script or not script.string:
        return detail

    payload = json.loads(script.string)
    graph = payload.get("@graph", [])
    index = _graph_index(graph)

    by_type: dict[str, dict[str, Any]] = {}
    for item in graph:
        item_type = item.get("@type")
        if item_type:
            by_type[item_type] = item

    listing = by_type.get("RealEstateListing", {})
    product = by_type.get("Product", {})
    offer = by_type.get("Offer", {})
    accommodation = by_type.get("Accommodation", {})

    address_ref = accommodation.get(
        "address") or by_type.get("Place", {}).get("address")
    address = _resolve_ref(address_ref, index) if address_ref else None

    price_spec = offer.get("priceSpecification", {})
    offered_by = _resolve_ref(offer.get("offeredBy"), index)

    detail["json_ld"] = {
        "real_estate_listing": {
            "url": listing.get("url"),
            "name": listing.get("name"),
            "description": listing.get("description"),
            "date_created": listing.get("dateCreated"),
            "date_published": listing.get("datePublished"),
            "date_modified": listing.get("dateModified"),
        },
        "product": {
            "name": product.get("name"),
            "description": product.get("description"),
            "category": product.get("category"),
            "images": _extract_images(product, index),
        },
        "offer": {
            "price_kes": price_spec.get("price"),
            "price_currency": price_spec.get("priceCurrency"),
            "availability": offer.get("availability"),
            "item_condition": offer.get("itemCondition"),
            "valid_from": offer.get("validFrom"),
            "valid_through": offer.get("validThrough"),
        },
        "accommodation": {
            "category": accommodation.get("accommodationCategory"),
            "bedrooms": accommodation.get("numberOfBedrooms"),
            "bathrooms": accommodation.get("numberOfBathroomsTotal"),
        },
        "address": {
            "street": address.get("streetAddress") if isinstance(address, dict) else None,
            "locality": address.get("addressLocality") if isinstance(address, dict) else None,
            "region": address.get("addressRegion") if isinstance(address, dict) else None,
            "country": address.get("addressCountry") if isinstance(address, dict) else None,
        },
        "agent": {
            "name": offered_by.get("name") if isinstance(offered_by, dict) else None,
            "id": offered_by.get("@id") if isinstance(offered_by, dict) else None,
        },
    }

    return detail
