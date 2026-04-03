"""
M2 Synthetic Data Generator
============================
Generates synthetic DC stock snapshot data with labeled shortage outcomes
for training an XGBoost-based 48-hour shortage predictor.

Each row represents a (DC, SKU, timestamp) observation with:
  - Stock levels (physical, in-transit, effective)
  - Sales velocity features (daily avg, 7-day trend, hourly rate)
  - Safety stock thresholds
  - Target label: will_shortage (1 if effective stock drops below safety stock within 48h)
  - Regression target: hours_until_shortage (capped at 48)

Usage:
    python generate_m2_data.py
"""

import pandas as pd
import numpy as np
import os

def generate_m2_training_data(
    output_path: str = "synthetic_m2_data.csv",
    num_rows: int = 5000,
    seed: int = 42,
):
    """
    Generate a rich synthetic dataset simulating DC stock snapshots
    for M2 shortage prediction.
    """
    np.random.seed(seed)

    # ------------------------------------------------------------------
    # Fixed universe (matches MVP scope)
    # ------------------------------------------------------------------
    dc_ids = [f"DC-{i:02d}" for i in range(1, 6)]       # 5 DCs
    sku_ids = [f"SKU-{i:03d}" for i in range(1, 16)]     # 15 SKUs
    sku_categories = {
        sku: np.random.choice(["analgesic", "antibiotic", "antiviral", "cardiac", "reefer"])
        for sku in sku_ids
    }

    rows = []
    for _ in range(num_rows):
        dc = np.random.choice(dc_ids)
        sku = np.random.choice(sku_ids)
        category = sku_categories[sku]

        # --- Sales velocity features ---
        avg_daily_sales = np.random.uniform(3, 120)
        # 7-day sales trend multiplier (0.6 = declining, 1.4 = surging)
        sales_trend_7d = np.random.uniform(0.6, 1.5)
        # Projected daily sales incorporating trend
        projected_daily_sales = avg_daily_sales * sales_trend_7d
        hourly_sales = projected_daily_sales / 24.0

        # --- Stock features ---
        physical_stock = max(0, int(np.random.normal(avg_daily_sales * 2.5, avg_daily_sales * 1.5)))
        in_transit_stock = int(np.random.exponential(avg_daily_sales * 0.8)) if np.random.rand() > 0.35 else 0
        effective_stock = physical_stock + in_transit_stock

        # Safety stock = ~half a day of projected sales
        safety_stock = max(1, int(projected_daily_sales * 0.5))

        # --- Stock ratio features (useful for ML) ---
        stock_to_sales_ratio = effective_stock / max(projected_daily_sales, 0.1)
        days_of_cover = effective_stock / max(projected_daily_sales, 0.1)

        # --- Temporal features ---
        day_of_week = np.random.randint(0, 7)  # 0=Mon ... 6=Sun
        is_weekend = 1 if day_of_week >= 5 else 0
        hour_of_day = np.random.randint(0, 24)

        # --- Lead time feature (hours until next scheduled delivery) ---
        lead_time_hours = np.random.choice([6, 12, 18, 24, 36, 48], p=[0.1, 0.2, 0.25, 0.25, 0.15, 0.05])

        # --- Compute ground-truth labels ---
        projected_48h_sales = hourly_sales * 48
        expected_stock_at_48h = effective_stock - projected_48h_sales

        # Will we breach safety stock within 48 hours?
        will_shortage = 1 if expected_stock_at_48h <= safety_stock else 0

        # How many hours until safety stock is breached?
        if hourly_sales > 0:
            hours_until_shortage = (effective_stock - safety_stock) / hourly_sales
            hours_until_shortage = np.clip(hours_until_shortage, 0, 48)
        else:
            hours_until_shortage = 48.0  # No sales = no shortage

        # Add some realistic noise to the label (5% label flip to simulate real-world noise)
        if np.random.rand() < 0.05:
            will_shortage = 1 - will_shortage

        rows.append({
            "dc_id": dc,
            "sku_id": sku,
            "category": category,
            "physical_stock": physical_stock,
            "in_transit_stock": in_transit_stock,
            "effective_stock": effective_stock,
            "avg_daily_sales": round(avg_daily_sales, 2),
            "sales_trend_7d": round(sales_trend_7d, 3),
            "projected_daily_sales": round(projected_daily_sales, 2),
            "hourly_sales": round(hourly_sales, 4),
            "safety_stock": safety_stock,
            "stock_to_sales_ratio": round(stock_to_sales_ratio, 3),
            "days_of_cover": round(days_of_cover, 2),
            "day_of_week": day_of_week,
            "is_weekend": is_weekend,
            "hour_of_day": hour_of_day,
            "lead_time_hours": lead_time_hours,
            "projected_48h_sales": round(projected_48h_sales, 2),
            "expected_stock_at_48h": round(expected_stock_at_48h, 2),
            "hours_until_shortage": round(hours_until_shortage, 2),
            "will_shortage": will_shortage,
        })

    df = pd.DataFrame(rows)

    # Ensure output directory exists
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    df.to_csv(output_path, index=False)

    # --- Summary ---
    shortage_pct = df["will_shortage"].mean() * 100
    print(f"✅ Generated {len(df)} rows -> {output_path}")
    print(f"   Shortage rate: {shortage_pct:.1f}%")
    print(f"   DCs: {df['dc_id'].nunique()}  |  SKUs: {df['sku_id'].nunique()}")
    print(f"   Features: {len(df.columns)} columns")
    print(f"\nSample rows:")
    print(df.head(5).to_string(index=False))
    return df


if __name__ == "__main__":
    # Smart path resolution — works from any directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output = os.path.join(script_dir, "synthetic_m2_data.csv")
    generate_m2_training_data(output_path=output)
