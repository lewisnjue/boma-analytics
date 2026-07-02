# House Price Modeling Report

## Data exploration summary
- Rows loaded: 20488
- Train rows: 16390
- Test rows: 4098
- Features used: bedrooms, bathrooms, bathrooms_per_bedroom, property_type, location, location_price_mean, location_price_median, location_count, location_property_type_interaction, location_county_interaction, location_bedrooms_interaction, location_bathrooms_interaction, bedrooms_bucket
- Excluded leakage or sparse features: floor_size_sqm (missing 86%), source, parking, county
- Data quality note: numeric features were median-imputed, categorical features were filled with Unknown, and the target price was log-transformed to reduce skew.
- Feature note: county was removed in favor of the more informative location field.

## Model comparison
- ridge: R2=0.440, MAE=1, RMSE=1
- extra_trees: R2=0.434, MAE=1, RMSE=1
- random_forest: R2=0.433, MAE=1, RMSE=1
- gradient_boosting: R2=0.397, MAE=1, RMSE=1

## Best model
- Selected model: ridge
- Test R2: 0.440
- Test MAE: 1
- Test RMSE: 1
- Best parameters: {"alpha": 0.5, "copy_X": true, "fit_intercept": true, "max_iter": null, "positive": false, "random_state": null, "solver": "auto", "tol": 0.0001}

## Notes
- The target price was modeled on the original currency scale after applying a log transform during training to stabilize the regression objective.
- The final model is saved to the models directory for later inference.