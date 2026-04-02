"""M2 Real Engine — XGBoost-backed DC Replenishment Request Generator.

Loads committed XGBoost classifier + regressor artifacts and runs inference
on live DB-backed features to produce contract-compatible M2 requests.

Adapter responsibilities:
1. Build live runtime features from DB-backed contracts
2. Run XGBoost inference (classifier + regressor)
3. Normalize output to planner contract format (urgency band + required_by)
4. Emit raw trace metadata for persistence/debugging
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.preprocessing import LabelEncoder

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════

PLANNING_HORIZON_HOURS = 48
BUFFER_DAYS = 2
DEFAULT_LEAD_TIME_HOURS = 24

# Features expected by the trained XGBoost models
NUMERIC_FEATURES = [
    "physical_stock",
    "in_transit_stock",
    "effective_stock",
    "avg_daily_sales",
    "sales_trend_7d",
    "projected_daily_sales",
    "hourly_sales",
    "safety_stock",
    "stock_to_sales_ratio",
    "days_of_cover",
    "day_of_week",
    "is_weekend",
    "hour_of_day",
    "lead_time_hours",
]

CATEGORICAL_FEATURES = ["category"]
ALL_FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES

# Urgency normalization thresholds (from Integrate-plan.md)
URGENCY_THRESHOLDS = [
    (75, "critical"),
    (50, "high"),
    (25, "medium"),
    (0, "low"),
]

# Required-by offsets (from Integrate-plan.md)
REQUIRED_BY_HOURS = {
    "critical": 12,
    "high": 24,
    "medium": 36,
    "low": 48,
}

# ═══════════════════════════════════════════════════════════════════════
# MODEL LOADING (singleton pattern)
# ═══════════════════════════════════════════════════════════════════════

_cached_models: dict = {}


def _get_artifact_dir() -> Path:
    """Resolve the path to committed model artifacts."""
    return Path(__file__).resolve().parents[5] / "ml" / "models" / "artifacts"


def _load_models() -> tuple[xgb.XGBClassifier, xgb.XGBRegressor]:
    """Load and cache the committed XGBoost artifacts."""
    if "clf" in _cached_models and "reg" in _cached_models:
        return _cached_models["clf"], _cached_models["reg"]

    artifact_dir = _get_artifact_dir()
    clf_path = artifact_dir / "m2_classifier.json"
    reg_path = artifact_dir / "m2_regressor.json"

    if not clf_path.exists() or not reg_path.exists():
        raise FileNotFoundError(
            f"M2 model artifacts not found at {artifact_dir}. "
            "Run `python ml/models/m2_model.py` to generate them."
        )

    logger.info(f"Loading M2 XGBoost classifier from {clf_path}")
    clf = xgb.XGBClassifier()
    clf.load_model(str(clf_path))

    logger.info(f"Loading M2 XGBoost regressor from {reg_path}")
    reg = xgb.XGBRegressor()
    reg.load_model(str(reg_path))

    _cached_models["clf"] = clf
    _cached_models["reg"] = reg
    return clf, reg


# ═══════════════════════════════════════════════════════════════════════
# FEATURE BUILDER — live DB contracts → model features
# ═══════════════════════════════════════════════════════════════════════


def _build_features(
    dc_stock_contracts: list[dict],
    sales_forecasts: list[dict],
) -> pd.DataFrame:
    """Build a feature DataFrame from live DB-backed contracts.

    Maps canonical DC/SKU identifiers from the platform into the exact
    feature shapes the XGBoost models were trained on.
    """
    now = datetime.now(timezone.utc)

    # Build stock lookup: (dc_id, sku_id) → stock info
    stock_lookup: dict[tuple[int, int], dict] = {}
    for dc_contract in dc_stock_contracts:
        dc_id = dc_contract["dc_id"]
        for item in dc_contract.get("items", []):
            stock_lookup[(dc_id, item["sku_id"])] = {
                "physical_stock": item.get("physical", 0),
                "in_transit_stock": item.get("in_transit", 0),
                "effective_stock": item.get("effective", 0),
            }

    # Build forecast lookup: (dc_id, sku_id) → forecast info
    forecast_lookup: dict[tuple[int, int], dict] = {}
    for fc in sales_forecasts:
        forecast_lookup[(fc["dc_id"], fc["sku_id"])] = fc

    rows = []
    for (dc_id, sku_id), fc in forecast_lookup.items():
        stock = stock_lookup.get((dc_id, sku_id), {
            "physical_stock": 0,
            "in_transit_stock": 0,
            "effective_stock": 0,
        })

        daily_avg = fc.get("daily_avg", 0)
        forecast_48h = fc.get("forecast_48h", 0)
        effective = stock["effective_stock"]

        # Derive features that the model expects
        hourly_sales = daily_avg / 24.0 if daily_avg > 0 else 0
        projected_daily = daily_avg  # simple proxy
        safety_stock_val = daily_avg * 3 if daily_avg > 0 else 50  # 3-day safety buffer
        stock_to_sales = (effective / daily_avg) if daily_avg > 0 else 999
        days_of_cover = (effective / daily_avg) if daily_avg > 0 else 999
        sales_trend_7d = fc.get("sales_trend_7d", 0)

        row = {
            "dc_id": dc_id,
            "sku_id": sku_id,
            "dc_code": fc.get("dc_code", "UNKNOWN"),
            "sku_code": fc.get("sku_code", "UNKNOWN"),
            "sku_name": fc.get("sku_name", "Unknown SKU"),
            "category": fc.get("category", "General"),
            # numeric features
            "physical_stock": stock["physical_stock"],
            "in_transit_stock": stock["in_transit_stock"],
            "effective_stock": effective,
            "avg_daily_sales": daily_avg,
            "sales_trend_7d": sales_trend_7d,
            "projected_daily_sales": projected_daily,
            "hourly_sales": hourly_sales,
            "safety_stock": safety_stock_val,
            "stock_to_sales_ratio": min(stock_to_sales, 999),
            "days_of_cover": min(days_of_cover, 999),
            "day_of_week": now.weekday(),
            "is_weekend": 1 if now.weekday() >= 5 else 0,
            "hour_of_day": now.hour,
            "lead_time_hours": fc.get("lead_time_hours", DEFAULT_LEAD_TIME_HOURS),
            # extras for post-processing
            "forecast_48h": forecast_48h,
        }
        rows.append(row)

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows)


# ═══════════════════════════════════════════════════════════════════════
# OUTPUT NORMALIZATION
# ═══════════════════════════════════════════════════════════════════════


def _normalize_urgency(urgency_score: float) -> str:
    """Convert numeric urgency score to categorical band per Integrate-plan.md."""
    for threshold, band in URGENCY_THRESHOLDS:
        if urgency_score >= threshold:
            return band
    return "low"


def _compute_required_by(urgency_band: str) -> str:
    """Compute required_by timestamp from urgency band per Integrate-plan.md."""
    hours = REQUIRED_BY_HOURS.get(urgency_band, 48)
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


# ═══════════════════════════════════════════════════════════════════════
# MAIN RUN FUNCTION — drop-in replacement for m2_stub.run()
# ═══════════════════════════════════════════════════════════════════════


def run(
    dc_stock_contracts: list[dict],
    sales_forecasts: list[dict],
) -> list[dict]:
    """Run M2 real XGBoost engine to generate DC replenishment requests.

    Same contract as m2_stub.run() but backed by real XGBoost inference.
    Returns list of dicts matching the planner contract plus trace fields.
    """
    logger.info("M2 Real Engine: Starting inference")

    # Load committed artifacts
    clf, reg = _load_models()

    # Build features from live DB inputs
    features_df = _build_features(dc_stock_contracts, sales_forecasts)

    if features_df.empty:
        logger.warning("M2 Real Engine: No features built — returning empty")
        return []

    # Prepare features for model
    df = features_df.copy()

    # Label-encode categoricals
    label_encoders = {}
    for col in CATEGORICAL_FEATURES:
        le = LabelEncoder()
        df[col + "_encoded"] = le.fit_transform(df[col].astype(str))
        label_encoders[col] = le

    # Build feature matrix
    feature_cols = NUMERIC_FEATURES[:]  # copy
    X = df[feature_cols].copy()
    # Replace the category column with encoded version
    X["category"] = df["category_encoded"]

    # Run inference
    pred_shortage = clf.predict(X)
    pred_shortage_prob = clf.predict_proba(X)[:, 1]
    pred_hours = np.clip(reg.predict(X), 0, 48)

    df["pred_will_shortage"] = pred_shortage
    df["shortage_probability"] = pred_shortage_prob
    df["hours_until_shortage"] = pred_hours

    # Compute urgency scores: 0h → 100, 48h → 0
    df["urgency_score"] = (
        100 - (df["hours_until_shortage"] / PLANNING_HORIZON_HOURS) * 100
    ).clip(0, 100).round(1)

    # Filter only predicted shortages
    shortages = df[df["pred_will_shortage"] == 1].copy()

    if shortages.empty:
        logger.info("M2 Real Engine: No shortages predicted, returning empty")
        return []

    # Compute requested quantities
    shortages["projected_48h_sales"] = shortages["hourly_sales"] * PLANNING_HORIZON_HOURS
    shortages["expected_stock_at_48h"] = shortages["effective_stock"] - shortages["projected_48h_sales"]
    shortages["requested_quantity"] = (
        shortages["safety_stock"]
        - shortages["expected_stock_at_48h"]
        + shortages["avg_daily_sales"] * BUFFER_DAYS
    ).clip(lower=1).astype(int)

    # Normalize output to planner contract
    requests = []
    for _, row in shortages.iterrows():
        urgency_band = _normalize_urgency(row["urgency_score"])
        required_by = _compute_required_by(urgency_band)

        requests.append({
            # Contract fields (same as stub)
            "dc_id": int(row["dc_id"]),
            "dc_code": row.get("dc_code", "UNKNOWN"),
            "sku_id": int(row["sku_id"]),
            "sku_code": row.get("sku_code", "UNKNOWN"),
            "sku_name": row.get("sku_name", "Unknown SKU"),
            "requested_quantity": int(row["requested_quantity"]),
            "urgency": urgency_band,
            "required_by": required_by,
            "current_stock": float(row["effective_stock"]),
            "forecast_48h": float(row.get("forecast_48h", 0)),
            "hours_coverage": float(row.get("days_of_cover", 0) * 24),
            # Trace fields (persisted for debugging/audit)
            "urgency_score": float(row["urgency_score"]),
            "shortage_probability": float(row["shortage_probability"]),
            "hours_until_shortage": float(row["hours_until_shortage"]),
            "effective_stock_at_run": float(row["effective_stock"]),
            "projected_48h_sales": float(row["projected_48h_sales"]),
            "safety_stock": float(row["safety_stock"]),
            "raw_features": {
                col: float(row[col]) if isinstance(row[col], (int, float, np.integer, np.floating)) else str(row[col])
                for col in NUMERIC_FEATURES
            },
        })

    # Sort by urgency (most urgent first)
    urgency_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    requests.sort(key=lambda x: (urgency_order.get(x["urgency"], 4), -x["urgency_score"]))

    logger.info(f"M2 Real Engine: Generated {len(requests)} shortage requests")
    return requests
