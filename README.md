# Boma Analytics

Boma Analytics is a house-price prediction project for Kenyan property listings. It combines web-scraped listing data, preprocessing, feature engineering, and regression modeling into a reproducible training workflow.

## Project goal

Predict residential property prices from structured listing features such as bedrooms, bathrooms, property type, and location.

## Current workflow

1. Scrape and store raw property listings.
2. Prepare a modeling-ready dataset and export it to data/boma_listings_modeling.csv.
3. Clean the data by removing rows with implausible prices and filtering to residential listings.
4. Engineer simple features such as bathrooms-per-bedroom and bedroom buckets.
5. Train and compare regression models with a held-out test split.

## Current modeling setup

The current training pipeline uses:
- log-transformed target prices for better skew handling
- median imputation and categorical imputation
- feature selection focused on the most informative residential fields
- a held-out test set for final evaluation

## Best performance so far

The best-performing model in the current setup is a ridge regression model trained on the cleaned and transformed data.

- Test R2: 0.440
- Test MAE: 0.576 (log-scale target)
- Test RMSE: 0.946 (log-scale target)

to be honest this is bad prediction , i will be impoving by collecting more data the data ihave is not 
good enough 
## Repository structure

- data/: modeling CSV input data
- reports/: exploration and modeling reports
- models/: trained model artifacts
- src/boma_analytics/: reusable training and preprocessing code
- tests/: regression tests for the training pipeline

