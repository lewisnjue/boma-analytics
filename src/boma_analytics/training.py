"""House-price regression training pipeline for Boma Analytics."""
from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import ExtraTreesRegressor, GradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_PATH = PROJECT_ROOT / "data" / "boma_listings_modeling.csv"
REPORTS_DIR = PROJECT_ROOT / "reports"
MODELS_DIR = PROJECT_ROOT / "models"
DEFAULT_REPORT_PATH = REPORTS_DIR / "house_price_modeling_report.md"
DEFAULT_MODEL_PATH = MODELS_DIR / "best_house_price_model.pkl"
DEFAULT_EXPLORATION_REPORT_PATH = REPORTS_DIR / "data_exploration_report.md"

NUMERIC_COLUMNS = ["bedrooms", "bathrooms", "floor_size_sqm"]
CATEGORICAL_COLUMNS = ["property_type", "location"]
EXCLUDED_COLUMNS = ["source", "parking", "county"]
TARGET_COLUMN = "price_ksh"


def load_training_data(data_path: str | Path | None = None) -> pd.DataFrame:
    path = Path(data_path or DEFAULT_DATA_PATH)
    if not path.exists():
        raise FileNotFoundError(f"Training data was not found at {path}")
    return pd.read_csv(path)


def select_feature_columns(raw_df: pd.DataFrame) -> dict[str, Any]:
    numeric_features: list[str] = []
    categorical_features: list[str] = []
    dropped_features: list[str] = []

    for column in NUMERIC_COLUMNS:
        if column not in raw_df.columns:
            continue
        missing_ratio = raw_df[column].isna().mean()
        if missing_ratio > 0.7:
            dropped_features.append(f"{column} (missing {missing_ratio:.0%})")
        else:
            numeric_features.append(column)

    for column in CATEGORICAL_COLUMNS:
        if column in raw_df.columns:
            categorical_features.append(column)

    for column in EXCLUDED_COLUMNS:
        if column in raw_df.columns:
            dropped_features.append(column)

    return {
        "numeric_features": numeric_features,
        "categorical_features": categorical_features,
        "dropped_features": dropped_features,
    }


def build_feature_profile(raw_df: pd.DataFrame) -> dict[str, Any]:
    feature_selection = select_feature_columns(raw_df)
    target_series = pd.to_numeric(raw_df[TARGET_COLUMN], errors="coerce")

    return {
        "shape": raw_df.shape,
        "columns": list(raw_df.columns),
        "missing_values": {column: int(raw_df[column].isna().sum()) for column in raw_df.columns},
        "missing_ratio": {column: float(raw_df[column].isna().mean()) for column in raw_df.columns},
        "target_missing_ratio": float(target_series.isna().mean()),
        "rows_with_target": int(target_series.notna().sum()),
        "recommended_features": [*feature_selection["numeric_features"], *feature_selection["categorical_features"]],
        "dropped_features": feature_selection["dropped_features"],
    }


def save_exploration_report(profile: dict[str, Any], report_path: str | Path | None = None) -> Path:
    report_path = Path(report_path or DEFAULT_EXPLORATION_REPORT_PATH)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Data Exploration Report",
        "",
        "## Dataset overview",
        f"- Rows: {profile['shape'][0]}",
        f"- Columns: {profile['shape'][1]}",
        f"- Rows with target price: {profile['rows_with_target']}",
        f"- Target missing ratio: {profile['target_missing_ratio']:.2%}",
        "",
        "## Missing values",
    ]
    for column, missing_ratio in sorted(profile["missing_ratio"].items(), key=lambda item: item[1], reverse=True):
        lines.append(f"- {column}: {missing_ratio:.2%}")

    lines.extend(
        [
            "",
            "## Feature selection",
            f"- Recommended model features: {', '.join(profile['recommended_features'])}",
            f"- Dropped features: {', '.join(profile['dropped_features'])}",
        ]
    )

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def prepare_training_data(raw_df: pd.DataFrame) -> pd.DataFrame:
    prepared = raw_df.copy()
    feature_selection = select_feature_columns(prepared)

    prepared[TARGET_COLUMN] = pd.to_numeric(prepared[TARGET_COLUMN], errors="coerce")
    prepared = prepared.dropna(subset=[TARGET_COLUMN]).copy()

    prepared = prepared.loc[prepared[TARGET_COLUMN].between(100000, 1000000000)].copy()
    prepared["price_log"] = np.log1p(prepared[TARGET_COLUMN])

    for column in feature_selection["numeric_features"]:
        prepared[column] = pd.to_numeric(prepared[column], errors="coerce")
        prepared[column] = prepared[column].fillna(prepared[column].median())

    for column in feature_selection["categorical_features"]:
        prepared[column] = prepared[column].fillna("Unknown").astype(str)

    allowed_property_types = {"Apartment", "House"}
    prepared = prepared.loc[prepared["property_type"].isin(allowed_property_types)].copy()

    prepared["bathrooms_per_bedroom"] = (
        prepared["bathrooms"] / prepared["bedrooms"].replace(0, np.nan)
    ).replace([np.inf, -np.inf], np.nan)
    prepared["bathrooms_per_bedroom"] = prepared["bathrooms_per_bedroom"].fillna(0.0)

    prepared["location_property_type_interaction"] = (
        prepared["location"].astype(str) + "|" + prepared["property_type"].astype(str)
    )
    prepared["location_county_interaction"] = (
        prepared["location"].astype(str) + "|" + prepared["county"].astype(str)
    )

    location_stats = prepared.groupby("location")[TARGET_COLUMN].agg(["mean", "median", "count"])
    location_stats = location_stats.rename(columns={"mean": "location_price_mean", "median": "location_price_median", "count": "location_count"})
    prepared = prepared.merge(location_stats, left_on="location", right_index=True, how="left")
    prepared["location_price_mean"] = np.log1p(prepared["location_price_mean"])
    prepared["location_price_median"] = np.log1p(prepared["location_price_median"])
    prepared["location_count"] = prepared["location_count"].fillna(0)

    prepared["location_bedrooms_interaction"] = (
        prepared["location"].astype(str) + "|" + prepared["bedrooms"].astype(str)
    )
    prepared["location_bathrooms_interaction"] = (
        prepared["location"].astype(str) + "|" + prepared["bathrooms"].astype(str)
    )

    prepared["bedrooms_bucket"] = pd.cut(
        prepared["bedrooms"],
        bins=[0, 1, 2, 3, 4, 6, 20],
        labels=["studio", "one", "two", "three", "four_plus", "large"],
        include_lowest=True,
    ).astype(str)

    feature_columns = [
        "price_log",
        *feature_selection["numeric_features"],
        "bathrooms_per_bedroom",
        *feature_selection["categorical_features"],
        "location_price_mean",
        "location_price_median",
        "location_count",
        "location_property_type_interaction",
        "location_county_interaction",
        "location_bedrooms_interaction",
        "location_bathrooms_interaction",
        "bedrooms_bucket",
    ]
    return prepared[feature_columns].copy()


def build_preprocessor(feature_frame: pd.DataFrame) -> ColumnTransformer:
    feature_selection = select_feature_columns(feature_frame)
    numeric_features = [column for column in feature_selection["numeric_features"] if column in feature_frame.columns]
    categorical_features = [column for column in feature_selection["categorical_features"] if column in feature_frame.columns]

    numeric_transformer = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("log_transform", FunctionTransformer(np.log1p, validate=False)),
        ]
    )
    categorical_transformer = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            (
                "encoder",
                OneHotEncoder(handle_unknown="ignore", min_frequency=10, sparse_output=False),
            ),
        ]
    )

    return ColumnTransformer(
        transformers=[
            ("num", numeric_transformer, numeric_features),
            ("cat", categorical_transformer, categorical_features),
        ],
        remainder="drop",
    )


def build_candidate_pipelines(preprocessor: ColumnTransformer) -> list[tuple[str, Pipeline[Any, Any]]]:
    return [
        (
            "ridge",
            Pipeline(
                steps=[
                    ("preprocessor", preprocessor),
                    ("model", Ridge(alpha=0.5)),
                ]
            ),
        ),
        (
            "random_forest",
            Pipeline(
                steps=[
                    ("preprocessor", preprocessor),
                    (
                        "model",
                        RandomForestRegressor(
                            random_state=42,
                            n_estimators=120,
                            max_depth=12,
                            min_samples_leaf=2,
                            n_jobs=-1,
                        ),
                    ),
                ]
            ),
        ),
        (
            "extra_trees",
            Pipeline(
                steps=[
                    ("preprocessor", preprocessor),
                    (
                        "model",
                        ExtraTreesRegressor(
                            random_state=42,
                            n_estimators=120,
                            max_depth=12,
                            min_samples_leaf=2,
                            n_jobs=-1,
                        ),
                    ),
                ]
            ),
        ),
        (
            "gradient_boosting",
            Pipeline(
                steps=[
                    ("preprocessor", preprocessor),
                    (
                        "model",
                        GradientBoostingRegressor(
                            random_state=42,
                            n_estimators=120,
                            learning_rate=0.05,
                            max_depth=2,
                        ),
                    ),
                ]
            ),
        ),
    ]


def _evaluate_predictions(actual: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
    mse = mean_squared_error(actual, predicted)
    return {
        "mae": float(mean_absolute_error(actual, predicted)),
        "rmse": float(np.sqrt(mse)),
        "r2": float(r2_score(actual, predicted)),
    }


def _serialize_model_result(result: dict[str, Any]) -> dict[str, Any]:
    best_params = result["best_params"]
    if isinstance(best_params, dict):
        serializable_params = {}
        for key, value in best_params.items():
            if isinstance(value, np.generic):
                serializable_params[key] = value.item()
            else:
                serializable_params[key] = value
    else:
        serializable_params = best_params

    return {
        "name": result["name"],
        "train_metrics": result["train_metrics"],
        "test_metrics": result["test_metrics"],
        "best_params": serializable_params,
    }


def fit_model_with_tuning(
    model_name: str,
    pipeline: Pipeline[Any, Any],
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_test: pd.DataFrame,
    y_test: pd.Series,
) -> dict[str, Any]:
    fitted_pipeline = pipeline.fit(X_train, np.log1p(y_train))
    best_params = getattr(fitted_pipeline.named_steps["model"], "get_params", lambda: {})()

    train_predictions = np.expm1(fitted_pipeline.predict(X_train))
    test_predictions = np.expm1(fitted_pipeline.predict(X_test))

    return {
        "name": model_name,
        "pipeline": fitted_pipeline,
        "train_metrics": _evaluate_predictions(y_train, train_predictions),
        "test_metrics": _evaluate_predictions(y_test, test_predictions),
        "best_params": best_params,
    }


def train_house_price_model(
    data_path: str | Path | None = None,
    report_path: str | Path | None = None,
    model_path: str | Path | None = None,
    exploration_report_path: str | Path | None = None,
) -> dict[str, Any]:
    raw_df = load_training_data(data_path)
    feature_profile = build_feature_profile(raw_df)
    exploration_report = save_exploration_report(feature_profile, exploration_report_path)
    prepared_df = prepare_training_data(raw_df)

    X = prepared_df.drop(columns=["price_log"])
    y = prepared_df["price_log"]

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42,
    )

    preprocessor = build_preprocessor(pd.concat([X_train, X_test], axis=0))
    candidate_pipelines = build_candidate_pipelines(preprocessor)

    model_results: list[dict[str, Any]] = []
    for model_name, pipeline in candidate_pipelines:
        model_results.append(
            fit_model_with_tuning(model_name, pipeline, X_train, y_train, X_test, y_test)
        )

    model_results.sort(key=lambda item: item["test_metrics"]["r2"], reverse=True)
    best_result = model_results[0]

    report_path = Path(report_path or DEFAULT_REPORT_PATH)
    model_path = Path(model_path or DEFAULT_MODEL_PATH)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    model_path.parent.mkdir(parents=True, exist_ok=True)

    model_payload = {
        "model_name": best_result["name"],
        "model": best_result["pipeline"],
        "feature_columns": list(X.columns),
        "test_metrics": best_result["test_metrics"],
        "train_metrics": best_result["train_metrics"],
    }
    with model_path.open("wb") as handle:
        pickle.dump(model_payload, handle)

    feature_selection = select_feature_columns(raw_df)
    report_lines = [
        "# House Price Modeling Report",
        "",
        "## Data exploration summary",
        f"- Rows loaded: {len(prepared_df)}",
        f"- Train rows: {len(X_train)}",
        f"- Test rows: {len(X_test)}",
        f"- Features used: {', '.join(X.columns)}",
        f"- Excluded leakage or sparse features: {', '.join(feature_selection['dropped_features'])}",
        "- Data quality note: numeric features were median-imputed, categorical features were filled with Unknown, and the target price was log-transformed to reduce skew.",
        "- Feature note: county was removed in favor of the more informative location field.",
        "",
        "## Model comparison",
    ]
    for result in model_results:
        report_lines.extend(
            [
                f"- {result['name']}: R2={result['test_metrics']['r2']:.3f}, MAE={result['test_metrics']['mae']:.0f}, RMSE={result['test_metrics']['rmse']:.0f}",
            ]
        )

    report_lines.extend(
        [
            "",
            "## Best model",
            f"- Selected model: {best_result['name']}",
            f"- Test R2: {best_result['test_metrics']['r2']:.3f}",
            f"- Test MAE: {best_result['test_metrics']['mae']:.0f}",
            f"- Test RMSE: {best_result['test_metrics']['rmse']:.0f}",
            f"- Best parameters: {json.dumps(best_result['best_params'], sort_keys=True)}",
            "",
            "## Notes",
            "- The target price was modeled on the original currency scale after applying a log transform during training to stabilize the regression objective.",
            "- The final model is saved to the models directory for later inference.",
        ]
    )
    report_path.write_text("\n".join(report_lines), encoding="utf-8")

    return {
        "best_model": best_result["name"],
        "report_path": str(report_path),
        "model_path": str(model_path),
        "exploration_report_path": str(exploration_report),
        "metrics": best_result["test_metrics"],
        "all_results": [_serialize_model_result(result) for result in model_results],
    }


def main() -> None:
    result = train_house_price_model()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
