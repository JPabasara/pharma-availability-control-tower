"""
M2 Model — XGBoost DC Request Generator
=========================================
Predicts 48-hour stock shortages at Distribution Centers and generates
prioritised replenishment requests using XGBoost.

Two prediction heads:
  1. **Classification** — will_shortage (binary: 1 = shortage expected)
  2. **Regression**     — hours_until_shortage (0–48 h, for urgency scoring)

Standalone usage (no project dependencies required):
    cd ml/models
    python m2_model.py

The script will:
  1. Load synthetic_m2_data.csv
  2. Train + evaluate both XGBoost models (classification & regression)
  3. Print evaluation metrics and feature importances
  4. Generate a ranked list of DC replenishment requests
  5. Save the trained models to ml/models/artifacts/
"""

import os
import sys
import warnings
import numpy as np
import pandas as pd
from pathlib import Path

# XGBoost
import xgboost as xgb

# Scikit-learn utilities
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    classification_report,
    confusion_matrix,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)
from sklearn.preprocessing import LabelEncoder

warnings.filterwarnings("ignore", category=UserWarning)

# ═══════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════

PLANNING_HORIZON_HOURS = 48
BUFFER_DAYS = 2          # extra days of stock when computing request qty
RANDOM_STATE = 42

# Features used by the model (no target leakage)
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

# Target columns
CLF_TARGET = "will_shortage"
REG_TARGET = "hours_until_shortage"


# ═══════════════════════════════════════════════════════════════════════
# DATA LOADING & PREPARATION
# ═══════════════════════════════════════════════════════════════════════

def load_dataset(csv_path: str) -> pd.DataFrame:
    """Load the synthetic M2 dataset."""
    if not os.path.exists(csv_path):
        raise FileNotFoundError(
            f"Dataset not found at: {csv_path}\n"
            "Run  python ../datasets/generate_m2_data.py  first."
        )
    df = pd.read_csv(csv_path)
    print(f"📥 Loaded {len(df)} rows from {csv_path}")
    return df


def prepare_features(df: pd.DataFrame, label_encoders: dict | None = None, fit: bool = True):
    """
    Encode categoricals and return (X, label_encoders).
    If fit=False, reuse existing encoders (for inference on new data).
    """
    df = df.copy()
    if label_encoders is None:
        label_encoders = {}

    for col in CATEGORICAL_FEATURES:
        if fit:
            le = LabelEncoder()
            df[col] = le.fit_transform(df[col].astype(str))
            label_encoders[col] = le
        else:
            le = label_encoders[col]
            # Handle unseen categories gracefully
            df[col] = df[col].astype(str).map(
                {v: i for i, v in enumerate(le.classes_)}
            ).fillna(-1).astype(int)

    X = df[NUMERIC_FEATURES + CATEGORICAL_FEATURES]
    return X, label_encoders


# ═══════════════════════════════════════════════════════════════════════
# MODEL TRAINING
# ═══════════════════════════════════════════════════════════════════════

def train_classifier(X_train, y_train, X_val, y_val) -> xgb.XGBClassifier:
    """Train XGBoost binary classifier for shortage prediction."""
    # Handle class imbalance via scale_pos_weight
    n_neg = (y_train == 0).sum()
    n_pos = (y_train == 1).sum()
    scale_pos_weight = n_neg / max(n_pos, 1)

    clf = xgb.XGBClassifier(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        scale_pos_weight=scale_pos_weight,
        eval_metric="logloss",
        random_state=RANDOM_STATE,
        use_label_encoder=False,
        verbosity=0,
    )

    clf.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        verbose=False,
    )
    return clf


def train_regressor(X_train, y_train, X_val, y_val) -> xgb.XGBRegressor:
    """Train XGBoost regressor for hours-until-shortage prediction."""
    reg = xgb.XGBRegressor(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        eval_metric="mae",
        random_state=RANDOM_STATE,
        verbosity=0,
    )

    reg.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        verbose=False,
    )
    return reg


# ═══════════════════════════════════════════════════════════════════════
# EVALUATION
# ═══════════════════════════════════════════════════════════════════════

def evaluate_classifier(clf, X_test, y_test):
    """Print classification metrics."""
    y_pred = clf.predict(X_test)
    y_prob = clf.predict_proba(X_test)[:, 1]

    print("\n" + "=" * 70)
    print("📊 CLASSIFICATION EVALUATION — will_shortage")
    print("=" * 70)
    print(f"  Accuracy:  {accuracy_score(y_test, y_pred):.4f}")
    print(f"  Precision: {precision_score(y_test, y_pred, zero_division=0):.4f}")
    print(f"  Recall:    {recall_score(y_test, y_pred, zero_division=0):.4f}")
    print(f"  F1 Score:  {f1_score(y_test, y_pred, zero_division=0):.4f}")
    print(f"  ROC AUC:   {roc_auc_score(y_test, y_prob):.4f}")
    print("\nConfusion Matrix:")
    cm = confusion_matrix(y_test, y_pred)
    print(f"  TN={cm[0,0]:4d}  FP={cm[0,1]:4d}")
    print(f"  FN={cm[1,0]:4d}  TP={cm[1,1]:4d}")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, target_names=["No Shortage", "Shortage"]))


def evaluate_regressor(reg, X_test, y_test):
    """Print regression metrics."""
    y_pred = reg.predict(X_test)

    print("=" * 70)
    print("📊 REGRESSION EVALUATION — hours_until_shortage")
    print("=" * 70)
    print(f"  MAE:  {mean_absolute_error(y_test, y_pred):.2f} hours")
    print(f"  RMSE: {np.sqrt(mean_squared_error(y_test, y_pred)):.2f} hours")
    print(f"  R²:   {r2_score(y_test, y_pred):.4f}")


def print_feature_importance(model, feature_names, title="Feature Importance"):
    """Print top features by XGBoost importance."""
    importances = model.feature_importances_
    sorted_idx = np.argsort(importances)[::-1]

    print(f"\n{'─' * 50}")
    print(f"  {title}")
    print(f"{'─' * 50}")
    for rank, idx in enumerate(sorted_idx[:10], 1):
        bar = "█" * int(importances[idx] * 40)
        print(f"  {rank:2d}. {feature_names[idx]:<28s} {importances[idx]:.4f}  {bar}")
    print()


# ═══════════════════════════════════════════════════════════════════════
# REQUEST GENERATION (post-prediction)
# ═══════════════════════════════════════════════════════════════════════

def generate_requests(df: pd.DataFrame, clf, reg, label_encoders: dict) -> pd.DataFrame:
    """
    Run both models on the full dataset and produce a ranked DataFrame
    of DC replenishment requests for items predicted to experience shortage.
    """
    X, _ = prepare_features(df, label_encoders=label_encoders, fit=False)

    # Predict
    df = df.copy()
    df["pred_will_shortage"] = clf.predict(X)
    df["pred_shortage_prob"] = clf.predict_proba(X)[:, 1]
    df["pred_hours_until_shortage"] = np.clip(reg.predict(X), 0, 48)

    # Filter only predicted shortages
    shortages = df[df["pred_will_shortage"] == 1].copy()

    if shortages.empty:
        return pd.DataFrame()

    # Urgency score: 0h → 100, 48h → 0
    shortages["urgency_score"] = (
        100 - (shortages["pred_hours_until_shortage"] / PLANNING_HORIZON_HOURS) * 100
    ).clip(0, 100).round(1)

    # Requested quantity: bring stock back to safety level + buffer
    shortages["projected_48h_sales"] = shortages["hourly_sales"] * PLANNING_HORIZON_HOURS
    shortages["expected_stock_at_48h"] = shortages["effective_stock"] - shortages["projected_48h_sales"]
    shortages["requested_quantity"] = (
        shortages["safety_stock"]
        - shortages["expected_stock_at_48h"]
        + shortages["avg_daily_sales"] * BUFFER_DAYS
    ).clip(lower=0).astype(int)

    # Build output
    requests = shortages[[
        "dc_id",
        "sku_id",
        "category",
        "urgency_score",
        "pred_shortage_prob",
        "pred_hours_until_shortage",
        "requested_quantity",
        "effective_stock",
        "projected_48h_sales",
        "safety_stock",
    ]].copy()

    requests.columns = [
        "dc_id",
        "sku_id",
        "category",
        "urgency_score",
        "shortage_probability",
        "hours_until_shortage",
        "requested_quantity",
        "effective_stock",
        "projected_48h_sales",
        "safety_stock",
    ]

    # Sort by urgency (most urgent first)
    requests = requests.sort_values(
        by=["urgency_score", "shortage_probability"],
        ascending=[False, False],
    ).reset_index(drop=True)

    return requests


# ═══════════════════════════════════════════════════════════════════════
# SAVE / LOAD MODELS
# ═══════════════════════════════════════════════════════════════════════

def save_models(clf, reg, output_dir: str):
    """Save both XGBoost models as JSON files."""
    os.makedirs(output_dir, exist_ok=True)
    clf_path = os.path.join(output_dir, "m2_classifier.json")
    reg_path = os.path.join(output_dir, "m2_regressor.json")
    clf.save_model(clf_path)
    reg.save_model(reg_path)
    print(f"💾 Models saved to {output_dir}/")
    print(f"   • Classifier: {clf_path}")
    print(f"   • Regressor:  {reg_path}")


def load_models(model_dir: str):
    """Load saved XGBoost models."""
    clf = xgb.XGBClassifier()
    clf.load_model(os.path.join(model_dir, "m2_classifier.json"))
    reg = xgb.XGBRegressor()
    reg.load_model(os.path.join(model_dir, "m2_regressor.json"))
    return clf, reg


# ═══════════════════════════════════════════════════════════════════════
# MAIN — full train → evaluate → predict pipeline
# ═══════════════════════════════════════════════════════════════════════

def main():
    print("🚀 M2 XGBoost DC Request Generator")
    print("=" * 70)

    # --- Resolve paths ---
    script_dir = Path(__file__).resolve().parent
    data_path = script_dir.parent / "datasets" / "synthetic_m2_data.csv"
    artifact_dir = script_dir / "artifacts"

    # --- Step 1: Load data ---
    df = load_dataset(str(data_path))

    # --- Step 2: Prepare features ---
    X, label_encoders = prepare_features(df, fit=True)
    y_clf = df[CLF_TARGET]
    y_reg = df[REG_TARGET]

    # --- Step 3: Train/test split ---
    X_train, X_test, y_clf_train, y_clf_test, y_reg_train, y_reg_test = train_test_split(
        X, y_clf, y_reg, test_size=0.2, random_state=RANDOM_STATE, stratify=y_clf
    )
    X_train, X_val, y_clf_train, y_clf_val, y_reg_train, y_reg_val = train_test_split(
        X_train, y_clf_train, y_reg_train, test_size=0.15, random_state=RANDOM_STATE, stratify=y_clf_train
    )

    print(f"\n📐 Split: Train={len(X_train)} | Val={len(X_val)} | Test={len(X_test)}")
    print(f"   Shortage rate — Train: {y_clf_train.mean():.1%} | Val: {y_clf_val.mean():.1%} | Test: {y_clf_test.mean():.1%}")

    # --- Step 4: Train models ---
    print("\n⚙️  Training XGBoost Classifier (will_shortage)...")
    clf = train_classifier(X_train, y_clf_train, X_val, y_clf_val)

    print("⚙️  Training XGBoost Regressor (hours_until_shortage)...")
    reg = train_regressor(X_train, y_reg_train, X_val, y_reg_val)

    # --- Step 5: Evaluate ---
    evaluate_classifier(clf, X_test, y_clf_test)
    evaluate_regressor(reg, X_test, y_reg_test)

    # --- Step 6: Feature importance ---
    feature_names = NUMERIC_FEATURES + CATEGORICAL_FEATURES
    print_feature_importance(clf, feature_names, "Classifier — Feature Importance")
    print_feature_importance(reg, feature_names, "Regressor — Feature Importance")

    # --- Step 7: Generate requests ---
    print("=" * 70)
    print("🔔 GENERATING DC REPLENISHMENT REQUESTS")
    print("=" * 70)
    requests_df = generate_requests(df, clf, reg, label_encoders)

    if requests_df.empty:
        print("✅ No shortages predicted — all DCs are well-stocked.")
    else:
        print(f"\n📋 {len(requests_df)} shortage requests generated\n")
        # Print top 20 most urgent
        print("Top 20 most urgent requests:")
        print(requests_df.head(20).to_string(index=False))

        # Save requests
        requests_path = str(script_dir / "artifacts" / "m2_requests_output.csv")
        os.makedirs(os.path.dirname(requests_path), exist_ok=True)
        requests_df.to_csv(requests_path, index=False)
        print(f"\n💾 Full requests saved to {requests_path}")

    # --- Step 8: Save models ---
    save_models(clf, reg, str(artifact_dir))

    print("\n" + "=" * 70)
    print("✅ M2 pipeline complete")
    print("=" * 70)


if __name__ == "__main__":
    main()
