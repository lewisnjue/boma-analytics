from pathlib import Path

import numpy as np
import pandas as pd

from boma_analytics.training import build_feature_profile, load_training_data, prepare_training_data


def test_load_training_data_reads_expected_columns():
    data_path = Path("data/boma_listings_modeling.csv")
    df = load_training_data(data_path)

    assert not df.empty
    assert "price_ksh" in df.columns
    assert {"bedrooms", "bathrooms", "parking", "floor_size_sqm"}.issubset(df.columns)


def test_prepare_training_data_drops_missing_targets_and_creates_feature_frame():
    raw_df = pd.DataFrame(
        {
            "price_ksh": [1000000, None, 2000000],
            "source": ["buyrentkenya", "property24", "buyrentkenya"],
            "property_type": ["Apartment", "House", "Apartment"],
            "bedrooms": [2, 3, 4],
            "bathrooms": [2, None, 1],
            "parking": [1, 0, None],
            "floor_size_sqm": [80.0, None, 110.0],
            "county": ["Nairobi", "Kiambu", "Nairobi"],
            "location": ["Westlands", "Ruiru", "Kilimani"],
        }
    )

    prepared = prepare_training_data(raw_df)
    profile = build_feature_profile(raw_df)

    assert prepared["price_log"].notna().all()
    assert prepared.shape[0] == 2
    assert {"property_type", "location", "bedrooms", "bathrooms", "floor_size_sqm"}.issubset(prepared.columns)
    assert "source" not in prepared.columns
    assert "parking" not in prepared.columns
    assert "county" not in prepared.columns
    assert "source" in profile["dropped_features"]
    assert "parking" in profile["dropped_features"]
    assert "county" in profile["dropped_features"]


def test_prepare_training_data_filters_extreme_prices_and_adds_engineered_features():
    raw_df = pd.DataFrame(
        {
            "price_ksh": [1000000, 2000000, 10000000000, 0],
            "source": ["buyrentkenya", "property24", "buyrentkenya", "property24"],
            "property_type": ["Apartment", "House", "Apartment", "Apartment"],
            "bedrooms": [2, 3, 4, 5],
            "bathrooms": [1, 1, 2, 3],
            "parking": [1, 0, None, 1],
            "floor_size_sqm": [80.0, None, 110.0, 90.0],
            "county": ["Nairobi", "Kiambu", "Nairobi", "Kiambu"],
            "location": ["Westlands", "Ruiru", "Kilimani", "Kikuyu"],
        }
    )

    prepared = prepare_training_data(raw_df)

    assert prepared.shape[0] == 2
    assert "bathrooms_per_bedroom" in prepared.columns
    assert prepared["price_log"].notna().all()
    assert prepared["price_log"].max() <= np.log1p(1000000000)
    assert "location_price_mean" in prepared.columns
    assert "location_count" in prepared.columns
    assert "location_property_type_interaction" in prepared.columns
    assert "location_county_interaction" in prepared.columns


def test_prepare_training_data_keeps_only_residential_property_types():
    raw_df = pd.DataFrame(
        {
            "price_ksh": [1000000, 2000000, 3000000],
            "source": ["buyrentkenya", "property24", "buyrentkenya"],
            "property_type": ["Apartment", "Land", "House"],
            "bedrooms": [2, 3, 4],
            "bathrooms": [1, 1, 2],
            "parking": [1, 0, None],
            "floor_size_sqm": [80.0, 120.0, 90.0],
            "county": ["Nairobi", "Kiambu", "Nairobi"],
            "location": ["Westlands", "Ruiru", "Kilimani"],
        }
    )

    prepared = prepare_training_data(raw_df)

    assert set(prepared["property_type"].unique()) <= {"Apartment", "House"}
    assert "price_log" in prepared.columns
