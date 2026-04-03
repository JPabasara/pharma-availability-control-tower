"""
M1 Model — Medicine Priority Tracker
====================================
Pure mathematical scoring engine. Reads simulated ship manifest lines,
evaluates warehouse stock buffers, checks ETA delays, and cross-references
against live M2 Request urgencies.

Outputs a ranked CSV of priority scores and priority bands for each manifest line.

Usage:
    cd ml/models
    python m1_model.py
"""

import os
import sys
import pandas as pd
import numpy as np
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════════
# CONFIGURATION & WEIGHTS (Adding up to 100 max points)
# ═══════════════════════════════════════════════════════════════════════

MAX_REEFER_BONUS = 40.0
MAX_M2_DEMAND_BONUS = 35.0
MAX_WH_BUFFER_PENALTY = 20.0
MAX_ETA_DELAY_BONUS = 15.0
MAX_RATIONING_BONUS = 10.0

MAX_SCORE = 100.0

# Priority Bands Thresholds
HIGH_THRESHOLD = 70.0
MEDIUM_THRESHOLD = 40.0

# ═══════════════════════════════════════════════════════════════════════
# LOGIC FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════

def load_manifest(csv_path: str) -> pd.DataFrame:
    """Load the synthetic incoming shipment data."""
    if not os.path.exists(csv_path):
        raise FileNotFoundError(
            f"Manifest dataset not found at: {csv_path}\n"
            "Run  python ../datasets/generate_m1_data.py  first."
        )
    df = pd.read_csv(csv_path)
    print(f"📥 Loaded {len(df)} manifest lines from incoming shipment")
    return df

def score_manifest(df: pd.DataFrame) -> pd.DataFrame:
    """Apply the mathematical priority engine to the manifest."""
    df = df.copy()
    
    # 1. Reefer Bonus (+40 max)
    # Cold chain is automatically massively higher priority
    df['score_reefer'] = df['reefer_required'].apply(lambda x: MAX_REEFER_BONUS if x == 1 else 0.0)
    
    # 2. M2 Demand Pull (+35 max)
    # Scales directly with how badly DCs are screaming for it (0-100 score / 100 * 35)
    df['score_m2'] = (df['max_m2_urgency'] / 100.0) * MAX_M2_DEMAND_BONUS
    df['score_m2'] = df['score_m2'].fillna(0.0)
    
    # 3. Warehouse Buffer Penalty (-20 max)
    # Max penalty if warehouse has 7+ days of stock. No penalty if empty.
    # We clip it to [0, 1] then multiply by the max penalty.
    wh_ratio = (df['wh_days_of_cover'] / 7.0).clip(upper=1.0, lower=0.0)
    df['score_wh_penalty'] = -(wh_ratio * MAX_WH_BUFFER_PENALTY)
    
    # 4. ETA Delay Bonus (+15 max)
    # Max bonus if the ship was 48+ hours late.
    eta_ratio = (df['eta_delay_hours'] / 48.0).clip(upper=1.0, lower=0.0)
    df['score_eta'] = eta_ratio * MAX_ETA_DELAY_BONUS
    
    # 5. Rationing Bonus (+10 max)
    # Only kicks in if `m2_fulfillment_ratio` < 0.5 (Shipment covers less than half of DC demands)
    ration_bonus = np.where(df['m2_fulfillment_ratio'] < 0.5, 
                            (1.0 - df['m2_fulfillment_ratio']) * MAX_RATIONING_BONUS, 
                            0.0)
    df['score_rationing'] = ration_bonus
    
    # --- Final Composition ---
    raw_score = (
        df['score_reefer'] + 
        df['score_m2'] + 
        df['score_wh_penalty'] + 
        df['score_eta'] + 
        df['score_rationing']
    )
    
    df['priority_score'] = raw_score.clip(lower=0.0, upper=MAX_SCORE).round(1)
    
    # Human-readable breakdown for the planner UI
    df['score_breakdown'] = (
        "Reefer(+" + df['score_reefer'].round(1).astype(str) + ") " +
        "M2(+" + df['score_m2'].round(1).astype(str) + ") " +
        "WH_Buf(" + df['score_wh_penalty'].round(1).astype(str) + ") " +
        "ETA(+" + df['score_eta'].round(1).astype(str) + ") " +
        "Ration(+" + df['score_rationing'].round(1).astype(str) + ")"
    )

    # Convert to Priority Bands
    conditions = [
        (df['priority_score'] >= HIGH_THRESHOLD),
        (df['priority_score'] >= MEDIUM_THRESHOLD)
    ]
    choices = ['HIGH', 'MEDIUM']
    df['priority_band'] = np.select(conditions, choices, default='LOW')
    
    return df

# ═══════════════════════════════════════════════════════════════════════
# MAIN 
# ═══════════════════════════════════════════════════════════════════════

def main():
    print("🚀 M1 Mathematical Scoring Engine (Priority Tracker)")
    print("=" * 70)

    # Resolve paths reliably
    script_dir = Path(__file__).resolve().parent
    data_path = script_dir.parent / "datasets" / "synthetic_m1_data.csv"
    artifact_dir = script_dir / "artifacts"
    
    # 1. Load Data
    try:
        manifest_df = load_manifest(str(data_path))
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        return

    # 2. Score Data
    print("\n⚙️  Applying 5-Point Mathematical Formula to Manifest...")
    scored_df = score_manifest(manifest_df)
    
    # 3. Format Output
    output_cols = [
        'manifest_line_id', 'sku_id', 'category', 'reefer_required', 
        'manifest_quantity', 'priority_score', 'priority_band', 'score_breakdown',
        'max_m2_urgency', 'num_dcs_requesting', 'wh_days_of_cover', 'eta_delay_hours'
    ]
    final_output = scored_df[output_cols].copy()
    
    # Sort logically for the warehouse floor (Highest Priority First)
    final_output = final_output.sort_values(
        by=['priority_score', 'manifest_quantity'], 
        ascending=[False, False]
    ).reset_index(drop=True)
    
    # Print Distribution
    print("=" * 50)
    print("📋 PRIORITY BAND DISTRIBUTION")
    print(final_output['priority_band'].value_counts().to_string())
    print("=" * 50)
    
    print("\n🔥 TOP 10 HIGHEST PRIORITY CONTAINERS TO UNLOAD:")
    print(final_output.head(10).to_string(index=False))
    
    # 4. Save
    os.makedirs(str(artifact_dir), exist_ok=True)
    out_path = artifact_dir / "m1_priority_output.csv"
    final_output.to_csv(out_path, index=False)
    
    print(f"\n💾 Full priority list saved to {out_path}")
    print("✅ M1 Engine Complete")

if __name__ == "__main__":
    main()
