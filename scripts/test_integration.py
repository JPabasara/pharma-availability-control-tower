"""Integration test: Full orchestration pipeline against live database.

Tests the complete Generate Plan flow:
1. Readers fetch live snapshots from seeded data
2. M2 generates replenishment requests
3. M1 scores manifest lines
4. M3 generates 3 candidate plans
5. Results are persisted to engine_runs, m1_results, m2_requests, m3_plan_versions
6. Planner flow: approve → reservations + transfers created
"""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from apps.api.app.dependencies.database import SessionLocal
from apps.api.app.orchestration.service import generate_plan
from apps.api.app.planner_flow.service import approve_plan, reject_plan
from demo_state.services import get_reservations, get_transfers, get_stock_summary
from storage.models import EngineRun, M1Result, M2Request, M3PlanVersion


def main():
    session = SessionLocal()

    try:
        # ── Step 1: Generate Plan ──────────────────────────────────────
        print("=" * 60)
        print("INTEGRATION TEST: Full Orchestration Pipeline")
        print("=" * 60)
        print()

        print("[1/5] Running generate_plan()...")
        result = generate_plan(session)

        print(f"  Orchestration time: {result['orchestration_time']}")
        print(f"  M2 run ID: {result['m2_run_id']} ({result['m2_requests_count']} requests)")
        print(f"  M1 run ID: {result['m1_run_id']} ({result['m1_results_count']} results)")
        print(f"  M3 run ID: {result['m3_run_id']} ({result['m3_plans_count']} plans)")
        print(f"  Input snapshots: {result['input_snapshot_ids']}")
        print()

        # ── Step 2: Verify DB persistence ──────────────────────────────
        print("[2/5] Verifying DB persistence...")
        engine_runs = session.query(EngineRun).count()
        m1_results = session.query(M1Result).count()
        m2_requests = session.query(M2Request).count()
        m3_plans = session.query(M3PlanVersion).count()

        print(f"  Engine runs in DB: {engine_runs}")
        print(f"  M1 results in DB:  {m1_results}")
        print(f"  M2 requests in DB: {m2_requests}")
        print(f"  M3 plan versions:  {m3_plans}")
        print()

        assert engine_runs >= 3, f"Expected >= 3 engine runs, got {engine_runs}"
        assert m1_results > 0, "Expected M1 results"
        assert m2_requests > 0, "Expected M2 requests"
        assert m3_plans >= 3, f"Expected >= 3 M3 plans, got {m3_plans}"

        # ── Step 3: Show M2 requests ───────────────────────────────────
        print("[3/5] M2 Replenishment Requests:")
        for req in result["m2_requests"][:5]:
            print(f"  DC {req['dc_code']} SKU {req['sku_code']}: "
                  f"qty={req['requested_quantity']}, urgency={req['urgency']}")
        if len(result["m2_requests"]) > 5:
            print(f"  ... and {len(result['m2_requests']) - 5} more")
        print()

        # ── Step 4: Show M1 results ────────────────────────────────────
        print("[4/5] M1 Priority Results (top 5):")
        for res in result["m1_results"][:5]:
            print(f"  SKU {res['sku_code']}: score={res['priority_score']}, "
                  f"band={res['priority_band']}")
        print()

        # ── Step 5: Show M3 plans ──────────────────────────────────────
        print("[5/5] M3 Candidate Plans:")
        for plan in result["m3_plans"]:
            total = sum(sum(i["quantity"] for i in s["items"]) for s in plan["stops"])
            print(f"  {plan['plan_name']}: score={plan['score']}, "
                  f"is_best={plan['is_best']}, stops={len(plan['stops'])}, "
                  f"total_loaded={total}")
        print()

        # ── Step 6: Test approve flow ──────────────────────────────────
        print("=" * 60)
        print("TESTING PLANNER FLOW: Approve Best Plan")
        print("=" * 60)
        print()

        # Find the best plan
        best_plan = None
        for plan in result["m3_plans"]:
            if plan.get("is_best"):
                best_plan = plan
                break

        if best_plan and "plan_version_id" in best_plan:
            pvid = best_plan["plan_version_id"]
            print(f"  Approving plan version ID {pvid}...")
            approve_result = approve_plan(session, pvid)
            print(f"  Result: {approve_result['message']}")
            print(f"  Reservations created: {approve_result.get('reservations_created', 0)}")
            print(f"  Transfers created: {approve_result.get('transfers_created', 0)}")
            print()

            # Verify reservations
            reservations = get_reservations(session, status="active")
            print(f"  Active reservations: {len(reservations)}")
            for r in reservations[:3]:
                print(f"    SKU {r['sku_code']}: {r['quantity_reserved']} reserved")
            print()

            # Verify transfers
            transfers = get_transfers(session, status="in_transit")
            print(f"  In-transit transfers: {len(transfers)}")
            for t in transfers[:3]:
                print(f"    {t['registration']} -> DC {t['dc_code']}: "
                      f"{t['quantity']} x {t['sku_code']}")
            print()

            # Verify stock summary
            summary = get_stock_summary(session)
            totals = summary["totals"]
            print(f"  Stock Summary:")
            print(f"    WH: physical={totals['total_wh_physical']}, "
                  f"reserved={totals['total_wh_reserved']}, "
                  f"effective={totals['total_wh_effective']}")
            print(f"    DC: physical={totals['total_dc_physical']}, "
                  f"in_transit={totals['total_dc_in_transit']}, "
                  f"effective={totals['total_dc_effective']}")

            # Try approving again (should fail — immutability)
            print()
            print("  Testing immutability (re-approve should fail)...")
            reapprove = approve_plan(session, pvid)
            print(f"  Result: {reapprove['message']}")
            assert not reapprove["success"], "Re-approve should have failed!"
        else:
            print("  No best plan found to approve.")
        print()

        # ── Step 7: Test reject flow ───────────────────────────────────
        print("=" * 60)
        print("TESTING PLANNER FLOW: Reject Non-Best Plan")
        print("=" * 60)
        for plan in result["m3_plans"]:
            if not plan.get("is_best") and "plan_version_id" in plan:
                pvid = plan["plan_version_id"]
                reject_result = reject_plan(session, pvid, notes="Testing rejection")
                print(f"  Rejected plan version {pvid}: {reject_result['message']}")
                break
        print()

        print("=" * 60)
        print("ALL INTEGRATION TESTS PASSED!")
        print("=" * 60)

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
