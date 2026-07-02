# Data Exploration Report

## Dataset overview
- Rows: 32218
- Columns: 9
- Rows with target price: 32151
- Target missing ratio: 0.21%

## Missing values
- floor_size_sqm: 86.13%
- parking: 78.83%
- bathrooms: 58.42%
- bedrooms: 30.00%
- price_ksh: 0.21%
- source: 0.00%
- county: 0.00%
- location: 0.00%
- property_type: 0.00%

## Feature selection
- Recommended model features: bedrooms, bathrooms, property_type, location
- Dropped features: floor_size_sqm (missing 86%), source, parking, county