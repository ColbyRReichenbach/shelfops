"""
Data Validation — Pandera schemas for ML pipeline data quality.

Three validation gates:
  1. TrainingDataSchema  — raw data before feature engineering
  2. FeaturesSchema      — output of create_features()
  3. PredictionSchema    — input to predict_demand()

Usage:
    from ml.validate import validate_training_data, validate_features
    validated_df = validate_training_data(raw_df)
    validated_features = validate_features(features_df, tier="cold_start")
"""

from typing import Literal

import pandas as pd
import pandera as pa
import structlog
from pandera import Check, Column, DataFrameSchema

from ml.features import COLD_START_FEATURE_COLS, PRODUCTION_FEATURE_COLS, FeatureTier

logger = structlog.get_logger()


# ──────────────────────────────────────────────────────────────────────
# 1. Training Data Schema (raw transactions before feature engineering)
# ──────────────────────────────────────────────────────────────────────

TrainingDataSchema = DataFrameSchema(
    columns={
        "date": Column(pa.DateTime, nullable=False, coerce=True),
        "store_id": Column(str, nullable=False, coerce=True),
        "product_id": Column(str, nullable=False, coerce=True),
        "quantity": Column(
            float,
            checks=[
                Check.ge(0, error="quantity must be non-negative"),
            ],
            nullable=False,
            coerce=True,
        ),
    },
    # Allow extra columns (category, promotion flags, etc.)
    strict=False,
    coerce=True,
    name="TrainingData",
)


# ──────────────────────────────────────────────────────────────────────
# 2. Features Schema (output of create_features, tier-dependent)
# ──────────────────────────────────────────────────────────────────────


def _build_features_schema(tier: FeatureTier) -> DataFrameSchema:
    """Build a Pandera schema for the specified feature tier."""
    feature_cols = COLD_START_FEATURE_COLS if tier == "cold_start" else PRODUCTION_FEATURE_COLS

    columns = {}
    for col in feature_cols:
        # All features should be numeric after create_features()
        columns[col] = Column(
            float,
            nullable=True,  # Some may be NaN before fillna
            coerce=True,
            required=False,  # Graceful: warn instead of fail if missing
        )

    # Target column must exist
    columns["quantity"] = Column(float, nullable=False, coerce=True)

    return DataFrameSchema(
        columns=columns,
        strict=False,
        coerce=True,
        name=f"Features_{tier}",
    )


# Pre-build both schemas
ColdStartFeaturesSchema = _build_features_schema("cold_start")
ProductionFeaturesSchema = _build_features_schema("production")


# ──────────────────────────────────────────────────────────────────────
# 3. Prediction Input Schema
# ──────────────────────────────────────────────────────────────────────

PredictionInputSchema = DataFrameSchema(
    columns={
        "store_id": Column(str, nullable=False, coerce=True),
        "product_id": Column(str, nullable=False, coerce=True),
        "date": Column(pa.DateTime, nullable=False, coerce=True),
    },
    strict=False,
    coerce=True,
    name="PredictionInput",
)


# ──────────────────────────────────────────────────────────────────────
# Validation Functions
# ──────────────────────────────────────────────────────────────────────


def validate_training_data(
    df: pd.DataFrame,
    raise_on_error: bool = True,
) -> pd.DataFrame:
    """
    Validate raw training data before feature engineering.

    Returns validated (and possibly coerced) DataFrame.
    Raises SchemaError if validation fails and raise_on_error=True.
    """
    logger.info(
        "validation.training_data",
        rows=len(df),
        columns=list(df.columns),
    )

    try:
        validated = TrainingDataSchema.validate(df, lazy=True)
        logger.info("validation.training_data.passed", rows=len(validated))
        return validated
    except pa.errors.SchemaErrors as e:
        logger.error(
            "validation.training_data.failed",
            n_errors=len(e.failure_cases),
            errors=e.failure_cases.to_dict("records")[:5],  # Log first 5
        )
        if raise_on_error:
            raise
        return df


def validate_features(
    df: pd.DataFrame,
    tier: FeatureTier = "cold_start",
    raise_on_error: bool = False,
) -> pd.DataFrame:
    """
    Validate feature DataFrame after create_features().

    Default: warn but don't fail (features may have NaN before fillna).
    """
    schema = ColdStartFeaturesSchema if tier == "cold_start" else ProductionFeaturesSchema

    logger.info(
        "validation.features",
        tier=tier,
        rows=len(df),
        expected_features=len(COLD_START_FEATURE_COLS if tier == "cold_start" else PRODUCTION_FEATURE_COLS),
    )

    try:
        validated = schema.validate(df, lazy=True)
        # Check feature coverage
        expected = set(COLD_START_FEATURE_COLS if tier == "cold_start" else PRODUCTION_FEATURE_COLS)
        actual = set(df.columns) & expected
        coverage = len(actual) / len(expected) * 100

        logger.info(
            "validation.features.passed",
            tier=tier,
            coverage_pct=round(coverage, 1),
            missing=sorted(expected - actual)[:5],
        )
        return validated

    except pa.errors.SchemaErrors as e:
        logger.warning(
            "validation.features.issues",
            tier=tier,
            n_errors=len(e.failure_cases),
            errors=e.failure_cases.to_dict("records")[:5],
        )
        if raise_on_error:
            raise
        return df


def validate_prediction_input(
    df: pd.DataFrame,
    raise_on_error: bool = True,
) -> pd.DataFrame:
    """Validate prediction input has required identifier columns."""
    try:
        validated = PredictionInputSchema.validate(df, lazy=True)
        logger.info("validation.prediction_input.passed", rows=len(validated))
        return validated
    except pa.errors.SchemaErrors as e:
        logger.error(
            "validation.prediction_input.failed",
            n_errors=len(e.failure_cases),
        )
        if raise_on_error:
            raise
        return df
