"""End-to-end ML Integration Test.

Tests all three real engines (M2, M1, M3) with synthetic contract data
to validate the full orchestration pipeline works correctly.

Usage:
    cd <project_root>
    .venv/Scripts/python scripts/test_ml_integration.py
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Set engine modes for testing
os.environ["M1_ENGINE_MODE"] = "real"
os.environ["M2_ENGINE_MODE"] = "real"
os.environ["M3_ENGINE_MODE"] = "real"

# ─── Test Data ──────────────────────────────────────────────────────

SAMPLE_DC_STOCK_CONTRACTS = [
    {
        "dc_id": 1,
        "dc_code": "DC-COL",
        "snapshot_id": 100,
        "items": [
            {"sku_id": 1, "sku_code": "PARA-500", "physical": 200, "in_transit": 50, "effective": 250},
            {"sku_id": 2, "sku_code": "AMOX-250", "physical": 30, "in_transit": 0, "effective": 30},
            {"sku_id": 3, "sku_code": "OMEP-20", "physical": 500, "in_transit": 100, "effective": 600},
        ],
    },
    {
        "dc_id": 2,
        "dc_code": "DC-KAN",
        "snapshot_id": 101,
        "items": [
            {"sku_id": 1, "sku_code": "PARA-500", "physical": 100, "in_transit": 0, "effective": 100},
            {"sku_id": 2, "sku_code": "AMOX-250", "physical": 10, "in_transit": 0, "effective": 10},
            {"sku_id": 4, "sku_code": "INSU-PEN", "physical": 20, "in_transit": 5, "effective": 25},
        ],
    },
]

SAMPLE_SALES_FORECASTS = [
    {"dc_id": 1, "sku_id": 1, "sku_code": "PARA-500", "sku_name": "Paracetamol 500mg",
     "dc_code": "DC-COL", "forecast_48h": 400, "daily_avg": 200, "sales_trend_7d": 0.1,
     "category": "Analgesic", "lead_time_hours": 18},
    {"dc_id": 1, "sku_id": 2, "sku_code": "AMOX-250", "sku_name": "Amoxicillin 250mg",
     "dc_code": "DC-COL", "forecast_48h": 100, "daily_avg": 50, "sales_trend_7d": -0.05,
     "category": "Antibiotic", "lead_time_hours": 18},
    {"dc_id": 1, "sku_id": 3, "sku_code": "OMEP-20", "sku_name": "Omeprazole 20mg",
     "dc_code": "DC-COL", "forecast_48h": 300, "daily_avg": 150, "sales_trend_7d": 0.02,
     "category": "Gastrointestinal", "lead_time_hours": 18},
    {"dc_id": 2, "sku_id": 1, "sku_code": "PARA-500", "sku_name": "Paracetamol 500mg",
     "dc_code": "DC-KAN", "forecast_48h": 300, "daily_avg": 150, "sales_trend_7d": 0.15,
     "category": "Analgesic", "lead_time_hours": 24},
    {"dc_id": 2, "sku_id": 2, "sku_code": "AMOX-250", "sku_name": "Amoxicillin 250mg",
     "dc_code": "DC-KAN", "forecast_48h": 80, "daily_avg": 40, "sales_trend_7d": 0.08,
     "category": "Antibiotic", "lead_time_hours": 24},
    {"dc_id": 2, "sku_id": 4, "sku_code": "INSU-PEN", "sku_name": "Insulin Pen",
     "dc_code": "DC-KAN", "forecast_48h": 50, "daily_avg": 25, "sales_trend_7d": 0.0,
     "category": "Insulin", "lead_time_hours": 24},
]

SAMPLE_MANIFEST_LINES = [
    {"manifest_line_id": 1, "sku_id": 1, "sku_code": "PARA-500", "quantity": 2000, "reefer_required": False},
    {"manifest_line_id": 2, "sku_id": 2, "sku_code": "AMOX-250", "quantity": 500, "reefer_required": False},
    {"manifest_line_id": 3, "sku_id": 3, "sku_code": "OMEP-20", "quantity": 1000, "reefer_required": False},
    {"manifest_line_id": 4, "sku_id": 4, "sku_code": "INSU-PEN", "quantity": 200, "reefer_required": True},
]

SAMPLE_WAREHOUSE_STOCK = {
    "snapshot_id": 200,
    "items": [
        {"sku_id": 1, "sku_code": "PARA-500", "physical": 5000, "reserved": 100, "effective": 4900, "reefer_required": False},
        {"sku_id": 2, "sku_code": "AMOX-250", "physical": 800, "reserved": 0, "effective": 800, "reefer_required": False},
        {"sku_id": 3, "sku_code": "OMEP-20", "physical": 3000, "reserved": 200, "effective": 2800, "reefer_required": False},
        {"sku_id": 4, "sku_code": "INSU-PEN", "physical": 300, "reserved": 10, "effective": 290, "reefer_required": True},
    ],
}

SAMPLE_SKU_METADATA = {
    1: {"id": 1, "code": "PARA-500", "name": "Paracetamol 500mg", "category": "Analgesic", "reefer_required": False},
    2: {"id": 2, "code": "AMOX-250", "name": "Amoxicillin 250mg", "category": "Antibiotic", "reefer_required": False},
    3: {"id": 3, "code": "OMEP-20", "name": "Omeprazole 20mg", "category": "Gastrointestinal", "reefer_required": False},
    4: {"id": 4, "code": "INSU-PEN", "name": "Insulin Pen", "category": "Insulin", "reefer_required": True},
}

SAMPLE_ETAS = [
    {"vessel_id": 1, "hours_until_arrival": 14, "vessel_name": "MV Pharma Star"},
]

SAMPLE_LORRY_STATE = {
    "snapshot_id": 300,
    "lorries": [
        {"lorry_id": 1, "registration": "WP-KA-1234", "lorry_type": "normal", "capacity_units": 2000,
         "day1_status": "available", "day2_status": "available"},
        {"lorry_id": 2, "registration": "WP-KB-5678", "lorry_type": "normal", "capacity_units": 1500,
         "day1_status": "available", "day2_status": "available"},
        {"lorry_id": 3, "registration": "WP-KC-9012", "lorry_type": "reefer", "capacity_units": 800,
         "day1_status": "available", "day2_status": "available"},
    ],
}

SAMPLE_ROUTE_GRAPH = [
    {"id": 1, "origin_type": "warehouse", "origin_id": 1, "destination_type": "dc", "destination_id": 1,
     "travel_time_hours": 3.5, "cost": 12000},
    {"id": 2, "origin_type": "warehouse", "origin_id": 1, "destination_type": "dc", "destination_id": 2,
     "travel_time_hours": 5.0, "cost": 18000},
]


# ─── Test Functions ─────────────────────────────────────────────────

def test_m2_real():
    """Phase 1: Test M2 real XGBoost engine."""
    print("\n" + "=" * 70)
    print("📊 PHASE 1 TEST: M2 Real XGBoost Engine")
    print("=" * 70)

    from apps.api.app.orchestration.real.m2_real import run

    results = run(SAMPLE_DC_STOCK_CONTRACTS, SAMPLE_SALES_FORECASTS)

    print(f"\n   Generated {len(results)} replenishment requests")

    # Validate contract shape
    for i, req in enumerate(results):
        assert "dc_id" in req, f"Missing dc_id in result {i}"
        assert "sku_id" in req, f"Missing sku_id in result {i}"
        assert "requested_quantity" in req, f"Missing requested_quantity in result {i}"
        assert "urgency" in req, f"Missing urgency in result {i}"
        assert "required_by" in req, f"Missing required_by in result {i}"
        assert req["urgency"] in ("critical", "high", "medium", "low"), \
            f"Invalid urgency band: {req['urgency']}"
        assert req["requested_quantity"] > 0, f"requested_quantity must be > 0"
        # Check trace fields
        assert "urgency_score" in req, f"Missing trace field urgency_score"
        assert "shortage_probability" in req, f"Missing trace field shortage_probability"
        assert "raw_features" in req, f"Missing trace field raw_features"

    if results:
        print(f"\n   Sample request:")
        sample = results[0]
        print(f"     DC {sample['dc_id']} / SKU {sample['sku_id']}")
        print(f"     Urgency: {sample['urgency']} (score: {sample['urgency_score']})")
        print(f"     Qty: {sample['requested_quantity']}")
        print(f"     P(shortage): {sample['shortage_probability']:.3f}")
        print(f"     Hours until: {sample['hours_until_shortage']:.1f}")

    print("\n   ✅ M2 Real Engine: ALL CHECKS PASSED")
    return results


def test_m1_real(m2_results):
    """Phase 2: Test M1 real mathematical engine."""
    print("\n" + "=" * 70)
    print("📊 PHASE 2 TEST: M1 Real Mathematical Engine")
    print("=" * 70)

    from apps.api.app.orchestration.real.m1_real import run

    results = run(
        SAMPLE_MANIFEST_LINES,
        SAMPLE_WAREHOUSE_STOCK,
        m2_results,
        SAMPLE_SKU_METADATA,
        SAMPLE_ETAS,
    )

    print(f"\n   Scored {len(results)} manifest lines")

    # Validate contract shape
    for i, res in enumerate(results):
        assert "manifest_line_id" in res, f"Missing manifest_line_id in result {i}"
        assert "sku_id" in res, f"Missing sku_id in result {i}"
        assert "priority_score" in res, f"Missing priority_score in result {i}"
        assert "priority_band" in res, f"Missing priority_band in result {i}"
        assert "reefer_required" in res, f"Missing reefer_required in result {i}"
        assert res["priority_band"] in ("critical", "high", "medium", "low"), \
            f"Invalid band: {res['priority_band']}"
        assert 0 <= res["priority_score"] <= 100, f"Score out of range: {res['priority_score']}"
        # Check trace fields
        assert "score_breakdown" in res, f"Missing score_breakdown"
        assert "raw_features" in res, f"Missing raw_features"

    print("\n   Priority distribution:")
    bands = {}
    for res in results:
        bands[res["priority_band"]] = bands.get(res["priority_band"], 0) + 1
    for band, count in sorted(bands.items()):
        print(f"     {band}: {count}")

    if results:
        top = results[0]
        print(f"\n   Top priority: SKU {top['sku_id']} ({top['sku_code']})")
        print(f"     Score: {top['priority_score']} ({top['priority_band']})")
        print(f"     Breakdown: {top['score_breakdown']}")

    print("\n   ✅ M1 Real Engine: ALL CHECKS PASSED")
    return results


def test_m3_real(m2_results):
    """Phase 3: Test M3 real OR-Tools engine."""
    print("\n" + "=" * 70)
    print("📊 PHASE 3 TEST: M3 Real OR-Tools Engine")
    print("=" * 70)

    from apps.api.app.orchestration.real.m3_real import run

    plans = run(
        m2_results,
        SAMPLE_WAREHOUSE_STOCK,
        SAMPLE_LORRY_STATE,
        SAMPLE_ROUTE_GRAPH,
        SAMPLE_SKU_METADATA,
    )

    print(f"\n   Generated {len(plans)} candidate plans")
    assert len(plans) == 3, f"Expected 3 plans, got {len(plans)}"

    for plan in plans:
        assert "version_number" in plan, "Missing version_number"
        assert "plan_name" in plan, "Missing plan_name"
        assert "score" in plan, "Missing score"
        assert "is_best" in plan, "Missing is_best"
        assert "runs" in plan, "Missing runs"
        assert "stops" in plan, "Missing stops"
        assert "summary" in plan, "Missing summary"
        # Trace fields
        assert "generation_strategy" in plan, "Missing generation_strategy"
        assert "objective_value" in plan, "Missing objective_value"
        assert "solver_trace" in plan, "Missing solver_trace"

        print(f"\n   {plan['plan_name']}:")
        print(f"     Score: {plan['score']}")
        print(f"     Strategy: {plan['generation_strategy']}")
        print(f"     Runs: {plan['summary']['total_runs']}")
        print(f"     Stops: {plan['summary']['total_stops']}")
        print(f"     Items loaded: {plan['summary']['total_items_loaded']}")
        print(f"     Solver: {plan['solver_trace'].get('solver', 'unknown')}")
        print(f"     Status: {plan['solver_trace'].get('status', 'unknown')}")

    # Verify Plan A is marked as best
    assert plans[0]["is_best"] is True, "Plan A should be is_best=True"
    assert plans[1]["is_best"] is False, "Plan B should be is_best=False"
    assert plans[2]["is_best"] is False, "Plan C should be is_best=False"

    # Verify runs have proper structure
    for plan in plans:
        for run_data in plan["runs"]:
            assert "lorry_id" in run_data
            assert "dispatch_day" in run_data
            assert run_data["dispatch_day"] in (1, 2)
            for stop in run_data["stops"]:
                assert "dc_id" in stop
                assert "stop_sequence" in stop
                assert "items" in stop
                for item in stop["items"]:
                    assert "sku_id" in item
                    assert "quantity" in item
                    assert item["quantity"] > 0

    print("\n   ✅ M3 Real Engine: ALL CHECKS PASSED")
    return plans


def test_engine_bridge():
    """Test that engine bridge correctly routes to real/stub."""
    print("\n" + "=" * 70)
    print("📊 ENGINE BRIDGE ROUTING TEST")
    print("=" * 70)

    from apps.api.app.orchestration.engine_bridge import get_engine_mode

    # Test per-engine mode
    os.environ["M1_ENGINE_MODE"] = "real"
    os.environ["M2_ENGINE_MODE"] = "stub"
    os.environ["M3_ENGINE_MODE"] = "real"

    assert get_engine_mode("m1") == "real"
    assert get_engine_mode("m2") == "stub"
    assert get_engine_mode("m3") == "real"

    # Test fallback
    del os.environ["M1_ENGINE_MODE"]
    os.environ["ENGINE_MODE"] = "stub"
    assert get_engine_mode("m1") == "stub"

    # Restore
    os.environ["M1_ENGINE_MODE"] = "real"
    os.environ["M2_ENGINE_MODE"] = "real"
    os.environ["M3_ENGINE_MODE"] = "real"

    print("   ✅ Engine bridge routing: ALL CHECKS PASSED")


# ─── Main ───────────────────────────────────────────────────────────

def main():
    print("🚀 ML Integration End-to-End Test")
    print("=" * 70)

    try:
        test_engine_bridge()
        m2_results = test_m2_real()
        m1_results = test_m1_real(m2_results)
        m3_plans = test_m3_real(m2_results)

        print("\n" + "=" * 70)
        print("🎉 ALL PHASES PASSED — ML Integration Complete!")
        print("=" * 70)
        print(f"\n   M2: {len(m2_results)} requests generated")
        print(f"   M1: {len(m1_results)} manifest lines scored")
        print(f"   M3: {len(m3_plans)} candidate plans generated")
        print(f"\n   Ready for deployment with:")
        print(f"     M1_ENGINE_MODE=real")
        print(f"     M2_ENGINE_MODE=real")
        print(f"     M3_ENGINE_MODE=real")

    except Exception as e:
        print(f"\n❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
