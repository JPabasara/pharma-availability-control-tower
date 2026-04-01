"""
M1 Synthetic Data Generator
============================
Generates synthetic ship manifest lines arriving at the port, merged with
simulated warehouse stock and live M2 urgency signals.

This acts as the input for the M1 Medicine Priority Tracker.
"""

import pandas as pd
import numpy as np
import os
import uuid

def generate_m1_data(
    m2_output_path: str = "../models/artifacts/m2_requests_output.csv",
    output_path: str = "synthetic_m1_data.csv",
    num_manifest_lines: int = 500,
    seed: int = 42
):
    np.random.seed(seed)
    
    # 1. Load M2 output to blend real urgency into the generator
    try:
        m2_df = pd.read_csv(m2_output_path)
    except FileNotFoundError:
        print(f"⚠️ Warning: M2 output not found at {m2_output_path}. Using empty mock M2 data.")
        m2_df = pd.DataFrame(columns=['sku_id', 'urgency_score', 'requested_quantity', 'category'])
        
    print(f"📥 Loaded {len(m2_df)} live M2 requests")

    # Aggregate M2 requests per SKU to understand total supply chain panic
    sku_m2_agg = m2_df.groupby('sku_id').agg(
        num_dcs_requesting=('sku_id', 'count'),
        max_m2_urgency=('urgency_score', 'max'),
        total_m2_requested_qty=('requested_quantity', 'sum')
    ).reset_index()

    # Create SKU categories mapping from M2 data if possible, else default
    if not m2_df.empty:
        sku_to_cat = dict(zip(m2_df['sku_id'], m2_df['category']))
    else:
        # Fallback if M2 is completely empty
        sku_ids = [f"SKU-{i:03d}" for i in range(1, 16)]
        cats = ["analgesic", "antibiotic", "antiviral", "cardiac", "reefer"]
        sku_to_cat = {sku: np.random.choice(cats) for sku in sku_ids}

    # All 15 known SKUs
    all_skus = [f"SKU-{i:03d}" for i in range(1, 16)]

    rows = []
    # 2. Simulate shipping containers arriving
    for i in range(num_manifest_lines):
        sku = np.random.choice(all_skus)
        category = sku_to_cat.get(sku, "general")
        reefer_required = 1 if category == "reefer" else 0
        
        # Determine how large the incoming shipment is (10 to 500 units)
        manifest_quantity = np.random.randint(10, 500)
        
        # Simulate Warehouse environment variables
        avg_daily_wh_outflow = np.random.uniform(5, 50)
        # Randomize warehouse stock: Could be empty (very bad) or overflowing (very safe)
        if np.random.rand() > 0.3:
            # Normal stock level (2 to 14 days of cover)
            wh_days_of_cover_sim = np.random.uniform(2, 14)
            warehouse_stock = int(avg_daily_wh_outflow * wh_days_of_cover_sim)
        else:
            # Zero or near-zero stock (crisis mode)
            warehouse_stock = np.random.randint(0, 10)
            
        wh_days_of_cover = warehouse_stock / avg_daily_wh_outflow
        
        # Shipping logistics
        # 70% chance of on-time, 30% chance of being delayed (1 to 72 hours late)
        eta_delay_hours = 0 if np.random.rand() < 0.7 else np.random.randint(1, 72)
        
        # Grab M2 stats
        m2_stats = sku_m2_agg[sku_m2_agg['sku_id'] == sku]
        if not m2_stats.empty:
            num_dcs_requesting = int(m2_stats['num_dcs_requesting'].values[0])
            max_m2_urgency = round(float(m2_stats['max_m2_urgency'].values[0]), 2)
            total_m2_requested_qty = int(m2_stats['total_m2_requested_qty'].values[0])
        else:
            # SKU is totally fine, no DC is requesting it
            num_dcs_requesting = 0
            max_m2_urgency = 0.0
            total_m2_requested_qty = 0
            
        # Calculate Fulfillment Ratio
        # (How much of the total M2 demand does this specific pallet cover?)
        if total_m2_requested_qty > 0:
            m2_fulfillment_ratio = round(manifest_quantity / total_m2_requested_qty, 3)
        else:
            m2_fulfillment_ratio = 1.0 # 100% fulfillment if demand is zero

        rows.append({
            "manifest_line_id": f"ML-{uuid.uuid4().hex[:8].upper()}",
            "sku_id": sku,
            "category": category,
            "reefer_required": reefer_required,
            "manifest_quantity": manifest_quantity,
            "warehouse_stock": warehouse_stock,
            "avg_daily_wh_outflow": round(avg_daily_wh_outflow, 2),
            "wh_days_of_cover": round(wh_days_of_cover, 2),
            "eta_delay_hours": eta_delay_hours,
            "num_dcs_requesting": num_dcs_requesting,
            "max_m2_urgency": max_m2_urgency,
            "total_m2_requested_qty": total_m2_requested_qty,
            "m2_fulfillment_ratio": m2_fulfillment_ratio
        })

    df = pd.DataFrame(rows)
    
    # Ensure dir exists
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        
    df.to_csv(output_path, index=False)
    
    print(f"✅ Generated {len(df)} manifest lines -> {output_path}")
    print("\nSample Data:")
    print(df[['sku_id', 'reefer_required', 'manifest_quantity', 'wh_days_of_cover', 'eta_delay_hours', 'max_m2_urgency']].head())

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_f = os.path.join(script_dir, "synthetic_m1_data.csv")
    m2_path = os.path.join(script_dir, "..", "models", "artifacts", "m2_requests_output.csv")
    
    generate_m1_data(m2_output_path=m2_path, output_path=output_f)
