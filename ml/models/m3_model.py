"""
M3 Engine — Candidate Dispatch Planner (Google OR-Tools)
========================================================
Solves the Multiple Knapsack & Vehicle Routing constraints to find the
mathematically perfect dispatch allocation of Warehouse Stock onto the Lorries.

Constraints applied:
1. Max capacity per lorry.
2. Max 2 DC stops per lorry.
3. Reefer cargo only to reefer trucks; Normal cargo only to normal trucks.
4. Cannot dispatch more than physically exists in Warehouse stock.
5. Cannot over-fulfill M2 requested quantities.

Objective: Maximize total dispatched urgency score.
"""

import os
import sys
import pandas as pd
import numpy as np
from pathlib import Path
from ortools.linear_solver import pywraplp

MAX_STOPS_PER_LORRY = 2

def load_data(script_dir: Path):
    datasets_dir = script_dir.parent / "datasets"
    artifacts_dir = script_dir / "artifacts"
    
    # Needs to handle missing files properly
    try:
        lorries_df = pd.read_csv(datasets_dir / "synthetic_m3_lorries.csv")
        wh_df = pd.read_csv(datasets_dir / "synthetic_m3_warehouse.csv")
        m2_df = pd.read_csv(artifacts_dir / "m2_requests_output.csv")
    except FileNotFoundError as e:
        print(f"❌ Missing file: {e}")
        print("Run `python ../datasets/generate_m2_data.py`")
        print("Run `python m2_model.py`")
        print("Run `python ../datasets/generate_m3_data.py`")
        sys.exit(1)
        
    # Pre-process M2 requests: We might have multiple simulated requests for the same DC+SKU combo.
    # Group them so we have 1 firm Demand target per DC, per SKU.
    m2_agg = m2_df.groupby(['dc_id', 'sku_id', 'category']).agg(
        requested_quantity=('requested_quantity', 'sum'),
        urgency_score=('urgency_score', 'max') # use max urgency for the target
    ).reset_index()
    
    # Filter out requests with 0 quantity
    m2_agg = m2_agg[m2_agg['requested_quantity'] > 0]
    
    return lorries_df, wh_df, m2_agg

def solve_m3(lorries_df, wh_df, m2_df):
    solver = pywraplp.Solver.CreateSolver('SCIP')
    if not solver:
        print("❌ Could not create SCIP solver.")
        return None
        
    print(f"⚙️  Building mathematical matrix for {len(lorries_df)} Lorries and {len(m2_df)} Requests...")

    # Data structures for speed
    lorries = lorries_df.to_dict('records')
    warehouse = wh_df.set_index('sku_id').to_dict('index')
    requests = m2_df.to_dict('records')
    
    DCs = list(m2_df['dc_id'].unique())
    SKUs = list(wh_df['sku_id'].unique())
    
    # ---------------------------------------------------------
    # DECISION VARIABLES
    # ---------------------------------------------------------
    # x[l, d, s] = Integer volume of SKU 's' loaded onto Lorry 'l' for DC 'd'
    x = {}
    for l_idx, lorry in enumerate(lorries):
        for d in DCs:
            for s in SKUs:
                x[(l_idx, d, s)] = solver.IntVar(0, solver.infinity(), f'x_{l_idx}_{d}_{s}')
                
    # y[l, d] = Binary 1 if Lorry 'l' stops at DC 'd', 0 otherwise
    y = {}
    for l_idx, lorry in enumerate(lorries):
        for d in DCs:
            y[(l_idx, d)] = solver.IntVar(0, 1, f'y_{l_idx}_{d}')
            
    # ---------------------------------------------------------
    # CONSTRAINTS
    # ---------------------------------------------------------
    
    # 1. Routing Constraint: A lorry can visit MAX 2 distinct DCs
    for l_idx, lorry in enumerate(lorries):
        solver.Add(sum(y[(l_idx, d)] for d in DCs) <= MAX_STOPS_PER_LORRY)
        
    # 2. Logic link: If we pack an item for DC 'd', then y[l, d] MUST be 1. 
    # Use big-M where M is the capacity of the lorry (max items it could theoretically carry)
    for l_idx, lorry in enumerate(lorries):
        for d in DCs:
            sum_items_for_d = sum(x[(l_idx, d, s)] for s in SKUs)
            solver.Add(sum_items_for_d <= lorry['capacity_units'] * y[(l_idx, d)])

    # 3. Lorry Capacity Constraint & Cold Chain Logic
    for l_idx, lorry in enumerate(lorries):
        total_lorry_volume = 0
        for d in DCs:
            for s in SKUs:
                sku_info = warehouse.get(s, {})
                sku_reefer = 1 if sku_info.get('reefer_required', 0) == 1 else 0
                is_reefer_lorry = 1 if lorry['lorry_type'] == 'reefer' else 0
                
                # Rule: Reefer items MUST go in reefer trucks
                if sku_reefer == 1 and is_reefer_lorry == 0:
                    solver.Add(x[(l_idx, d, s)] == 0)
                
                # Rule: Normal items MUST go in normal trucks (reserve reefer for reefers)
                if sku_reefer == 0 and is_reefer_lorry == 1:
                    solver.Add(x[(l_idx, d, s)] == 0)
                    
                total_lorry_volume += x[(l_idx, d, s)]
                
        # Total packed cannot exceed literal truck space
        solver.Add(total_lorry_volume <= lorry['capacity_units'])

    # 4. Inventory Constraint: Cannot dispatch more than we physically have in warehouse
    for s in SKUs:
        total_sku_loaded = sum(x[(l_idx, d, s)] for l_idx in range(len(lorries)) for d in DCs)
        avail_stock = warehouse.get(s, {}).get('effective_stock', 0)
        solver.Add(total_sku_loaded <= avail_stock)
        
    # 5. Demand Constraint: Cannot over-fulfill M2 requested quantities per DC
    for idx, req in enumerate(requests):
        d = req['dc_id']
        s = req['sku_id']
        max_requested = req['requested_quantity']
        total_sku_to_dc = sum(x[(l_idx, d, s)] for l_idx in range(len(lorries)))
        solver.Add(total_sku_to_dc <= max_requested)

    # ---------------------------------------------------------
    # OBJECTIVE
    # ---------------------------------------------------------
    # Maximize (Quantity Shipped * Demand Urgency)
    
    # Pre-map urgency
    urgency_map = {}
    for req in requests:
        urgency_map[(req['dc_id'], req['sku_id'])] = req['urgency_score']

    objective = solver.Objective()
    for l_idx in range(len(lorries)):
        for d in DCs:
            for s in SKUs:
                # If there's no M2 request, urgency is 0 (we shouldn't blind-ship it)
                urg = urgency_map.get((d, s), 0.0)
                objective.SetCoefficient(x[(l_idx, d, s)], float(urg))
                
    objective.SetMaximization()
    
    print("📈 Solving OR-Tools Mixed Integer Program...")
    status = solver.Solve()
    
    if status == pywraplp.Solver.OPTIMAL or status == pywraplp.Solver.FEASIBLE:
        print(f"✅ Solve complete! Objective Value (Utility): {objective.Value():.1f}")
        
        # Extract Results
        results = []
        for l_idx, lorry in enumerate(lorries):
            for d in DCs:
                for s in SKUs:
                    qty = int(x[(l_idx, d, s)].solution_value())
                    if qty > 0:
                        results.append({
                            "lorry_id": lorry["lorry_id"],
                            "lorry_type": lorry["lorry_type"],
                            "dc_id": d,
                            "sku_id": s,
                            "category": warehouse[s]['category'],
                            "quantity_dispatched": qty
                        })
        return pd.DataFrame(results)
    else:
        print("❌ The solver could not find an optimal solution.")
        return pd.DataFrame()

def main():
    print("🚀 M3 OR-Tools Engine (Candidate Dispatch Planner)")
    print("=" * 70)
    
    script_dir = Path(__file__).resolve().parent
    lorries_df, wh_df, m2_df = load_data(script_dir)
    
    plan_df = solve_m3(lorries_df, wh_df, m2_df)
    
    if plan_df is not None and not plan_df.empty:
        artifacts_dir = script_dir / "artifacts"
        os.makedirs(str(artifacts_dir), exist_ok=True)
        
        # Sort output safely for printing
        plan_df = plan_df.sort_values(by=['lorry_id', 'dc_id', 'sku_id'])
        
        out_path = artifacts_dir / "m3_dispatch_plan.csv"
        plan_df.to_csv(out_path, index=False)
        
        print("\n📊 M3 DISPATCH PLAN SUMMARY:")
        summary = plan_df.groupby(['lorry_id', 'lorry_type']).agg(
            total_items=('quantity_dispatched', 'sum'),
            stops=('dc_id', 'nunique')
        ).reset_index()
        print(summary.to_string(index=False))
        
        print(f"\n💾 Full dispatch routing saved to {out_path}")
    else:
        print("⚠️ No dispatches generated. Check warehouse stock vs demand.")

if __name__ == "__main__":
    main()
