from pathlib import Path

import pytest
from boma_analytics.sources import (
    BuyRentKenyaClient,
    BuyRentKenyaConfig,
)
from boma_analytics.sources.buyrentkenya import (
    parse_listing_card,
    parse_price_kes
)
from boma_analytics.sources.property24 import (
    parse_property24_listing_card,
)


FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def search_page_html() -> str:
    return (FIXTURES / "search_page_snippet.html").read_text(encoding="utf-8")


def test_parse_price_kes():
    assert parse_price_kes("KSh 17,500,000") == 17500000
    assert parse_price_kes(None) is None


def test_parse_listing_card(search_page_html):
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(search_page_html, "html.parser")
    card = soup.select_one(".listing-card")
    record = parse_listing_card(card, source_page=1)

    assert record.listing_id == "3826286"
    assert record.title == "4 Bed House with En Suite at Ruiru"
    assert record.price_kes == 17500000
    assert record.location == "Kamakis, Ruiru"
    assert record.bedrooms == 4
    assert record.bathrooms == 5
    assert record.area_sqm == 240.0
    assert "4 Bedrooms" in record.feature_badges


def test_get_total_pages(search_page_html):
    from bs4 import BeautifulSoup

    config = BuyRentKenyaConfig()
    client = BuyRentKenyaClient(config)
    soup = BeautifulSoup(search_page_html, "html.parser")
    assert client.get_total_pages(soup) == 102


def test_parse_property24_listing_card():
    from bs4 import BeautifulSoup

    fixture_path = FIXTURES / "property24_card_snippet.html"
    html = fixture_path.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    card = soup.select_one(".p24_regularTile")

    record = parse_property24_listing_card(card, source_page=1)

    assert record.listing_id == "117331226"
    assert record.title == "3 Bedroom Apartment / Flat"
    assert record.price_kes == 40000000
    assert record.location == "Westlands"
    assert record.address == "23 David Osieli Rd, Westlands, Nairobi"
    assert record.bedrooms == 3
    assert record.bathrooms == 3
    assert record.area_sqm == 155.0
    assert "3 Bedrooms" in record.feature_badges
