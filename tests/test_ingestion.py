from pathlib import Path

import pytest

from boma_analytics.ingestion import (
    BuyRentKenyaClient,
    BuyRentKenyaConfig,
    parse_listing_card,
    parse_price_kes,
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
