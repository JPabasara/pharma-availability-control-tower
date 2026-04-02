"""
M3 Synthetic Data Generator
============================
Generates synthetic data for the vehicle fleet and warehouse stock levels
to act as physical constraints for the M3 OR-Tools Optimizer.
"""

import pandas as pd
import numpy as np
import os

def generate_m3_data(
    m2_output_path: str = "../models/artifacts/m2_requests_output.csv",
    output_dir: str = ".",
    seed: int = 42
):
    np.random.seed(seed)
    os.makedirs(output_dir, exist_ok=True)
    
    # ---------------------------------------------------------
    # 1. Lorries Fleet
    # 8 Total: 5 Normal (500 cap), 3 Reefer (350 cap)
    # ---------------------------------------------------------
    lorries = [
        {"lorry_id": "L-01", "lorry_type": "normal", "capacity_units": 500},
        {"lorry_id": "L-02", "lorry_type": "normal", "capacity_units": 500},
        {"lorry_id": "L-03", "lorry_type": "normal", "capacity_units": 500},
        {"lorry_id": "L-04", "lorry_type": "normal", "capacity_units": 500},
        {"lorry_id": "L-05", "lorry_type": "normal", "capacity_units": 500},
        {"lorry_id": "L-R1", "lorry_type": "reefer", "capacity_units": 350},
        {"lorry_id": "L-R2", "lorry_type": "reefer", "capacity_units": 350},
        {"lorry_id": "L-R3", "lorry_type": "reefer", "capacity_units": 350},
    ]
    df_lorries = pd.DataFrame(lorries)
    lorries_path = os.path.join(output_dir, "synthetic_m3_lorries.csv")
    df_lorries.to_csv(lorries_path, index=False)
    print(f"✅ Generated {len(df_lorries)} Lorries Fleet -> {lorries_path}")

    # ---------------------------------------------------------
    # 2. Warehouse Stock Snapshot
    # Extract SKU list and categories from M2 to ensure consistency
    # ---------------------------------------------------------
    try:
        m2_df = pd.read_csv(m2_output_path)
        sku_cat_map = m2_df.drop_duplicates('sku_id').set_index('sku_id')['category'].to_dict()
    except FileNotFoundError:
        print(f"⚠️ M2 output not found at {m2_output_path}. Using fallback.")
        sku_ids = [f"SKU-{i:03d}" for i in range(1, 16)]
        cats = ["analgesic", "antibiotic", "antiviral", "cardiac", "reefer"]
        sku_cat_map = {sku: np.random.choice(cats) for sku in sku_ids}
        # ensure at least some reefer
        sku_cat_map["SKU-002"] = "reefer"
        sku_cat_map["SKU-004"] = "reefer"
        sku_cat_map["SKU-005"] = "reefer"

    wh_items = []
    for sku, cat in sku_cat_map.items():
        # Physical stock varies randomly, 0 to 5000 units
        # Simulate that sometimes inventory is critically short
        if np.random.rand() < 0.2:
            effective_stock = np.random.randint(0, 100) # Shortage in warehouse!
        else:
            effective_stock = np.random.randint(500, 5000)
            
        reefer_req = 1 if cat == "reefer" else 0
        
        wh_items.append({
            "sku_id": sku,
            "category": cat,
            "reefer_required": reefer_req,
            "effective_stock": effective_stock
        })
        
    df_wh = pd.DataFrame(wh_items)
    wh_path = os.path.join(output_dir, "synthetic_m3_warehouse.csv")
    df_wh.to_csv(wh_path, index=False)
    print(f"✅ Generated Warehouse Stock for {len(df_wh)} SKUs -> {wh_path}")
    print("\nWarehouse Stock Sample:")
    print(df_wh.head())

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    m2_path = os.path.join(script_dir, "..", "models", "artifacts", "m2_requests_output.csv")
    generate_m3_data(m2_output_path=m2_path, output_dir=script_dir)
