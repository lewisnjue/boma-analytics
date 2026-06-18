"""Source-specific ingestion clients for Boma Analytics."""

from .buyrentkenya import (
    BuyRentKenyaClient,
    BuyRentKenyaConfig,
    ListingRecord as BuyRentKenyaListingRecord,
    parse_listing_card as parse_buyrentkenya_listing_card,
    parse_price_kes as parse_buyrentkenya_price_kes,
)
from .property24 import (
    Property24Client,
    Property24Config,
    Property24ListingRecord,
    parse_property24_listing_card,
    parse_property24_detail,
)

__all__ = [
    "BuyRentKenyaClient",
    "BuyRentKenyaConfig",
    "BuyRentKenyaListingRecord",
    "parse_buyrentkenya_listing_card",
    "parse_buyrentkenya_price_kes",
    "Property24Client",
    "Property24Config",
    "Property24ListingRecord",
    "parse_property24_listing_card",
    "parse_property24_detail",
]
