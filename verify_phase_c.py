"""Full end-to-end verification of Phase C CLI scripts.

Each step uses a FRESH session to avoid stale-state problems.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from apps.api.app.dependencies.database import SessionLocal
from storage.models import (
    ManifestSnapshot, WarehouseStockSnapshot, WarehouseStockItem,
    DemoTransfer, DemoReservation, DemoArrivalEvent,
    DCStockSnapshot, DCStockItem, M3PlanVersion,
)
from sqlalchemy import desc
from sqlalchemy.orm import joinedload


class Results:
    passed = 0
    failed = 0


def check(label, success, detail=""):
    status = "PASS" if success else "FAIL"
    print(f"  [{status}] {label}")
    if detail and not success:
        print(f"         {detail}")
    if success:
        Results.passed += 1
    else:
        Results.failed += 1


def step1_reactivate_manifests():
    """Re-activate manifests so vessel arrival has work to do."""
    print("[Step 1] Re-activating manifests for test...")
    s = SessionLocal()
    try:
        manifests = s.query(ManifestSnapshot).all()
        for m in manifests:
            m.status = "active"
        s.commit()
        check(f"Re-activated {len(manifests)} manifests", len(manifests) > 0)
    finally:
        s.close()


def step2_capture_wh_stock_before():
    """Capture WH stock quantities before vessel arrival."""
    s = SessionLocal()
    try:
        wh_snap = (
            s.query(WarehouseStockSnapshot)
            .options(joinedload(WarehouseStockSnapshot.items))
            .order_by(desc(WarehouseStockSnapshot.snapshot_time))
            .first()
        )
        stock = {}
        if wh_snap:
            for item in wh_snap.items:
                stock[item.sku_id] = item.physical_quantity
        return stock
    finally:
        s.close()


def step3_run_vessel_arrival():
    """Run simulate_vessel_arrival and verify results."""
    print("\n[Step 2] Running vessel arrival simulation...")
    s = SessionLocal()
    try:
        from scripts.simulate_vessel_arrival import simulate_vessel_arrival
        result = simulate_vessel_arrival(s)
        check("Vessel arrival executed", result["success"], result.get("message", ""))
        check(f"Vessels arrived: {result.get('arrived', 0)}", result.get("arrived", 0) > 0)
        return result
    except Exception as e:
        check("Vessel arrival executed", False, str(e))
        return {"success": False, "arrived": 0}
    finally:
        s.close()


def step4_verify_wh_stock_changed(stock_before):
    """Verify WH stock increased after vessel arrival."""
    s = SessionLocal()
    try:
        wh_snap = (
            s.query(WarehouseStockSnapshot)
            .options(joinedload(WarehouseStockSnapshot.items))
            .order_by(desc(WarehouseStockSnapshot.snapshot_time))
            .first()
        )
        if wh_snap:
            for item in wh_snap.items:
                if item.physical_quantity > stock_before.get(item.sku_id, 0):
                    check("WH physical stock increased after vessel arrival", True)
                    return
        check("WH physical stock increased after vessel arrival", False, "No increase detected")
    finally:
        s.close()


def step5_verify_vessel_events():
    """Verify manifests are arrived and events created."""
    s = SessionLocal()
    try:
        arrived = s.query(ManifestSnapshot).filter(ManifestSnapshot.status == "arrived").count()
        check(f"Manifests marked as arrived: {arrived}", arrived > 0)

        events = s.query(DemoArrivalEvent).filter(
            DemoArrivalEvent.event_type == "vessel_arrival"
        ).count()
        check(f"Vessel arrival events created: {events}", events > 0)
    finally:
        s.close()


def step5b_drain_dc_stock():
    """Drain DC stock so M2 generates requests."""
    print("[Step 2b] Draining DC stock...")
    s = SessionLocal()
    try:
        items = s.query(DCStockItem).all()
        for item in items:
            item.physical_quantity = 0
            item.effective_quantity = 0
        s.commit()
    finally:
        s.close()


def step6_generate_and_approve_plan():
    """Generate a plan and approve the best one to create transfers."""
    print("\n[Step 3] Generating and approving a plan...")

    # Re-activate manifests for orchestration
    s = SessionLocal()
    try:
        for m in s.query(ManifestSnapshot).all():
            m.status = "active"
        s.commit()
    finally:
        s.close()

    # Generate plan in a fresh session
    m3_run_id = None
    s = SessionLocal()
    try:
        from apps.api.app.orchestration.service import generate_plan
        result = generate_plan(s)
        check("Plan generated", "m3_run_id" in result)
        m3_run_id = result.get("m3_run_id")
    except Exception as e:
        check("Plan generated", False, str(e))
        return
    finally:
        s.close()

    if not m3_run_id:
        return

    # Find best plan and approve in a fresh session
    s = SessionLocal()
    try:
        plans = s.query(M3PlanVersion).filter(
            M3PlanVersion.engine_run_id == m3_run_id
        ).all()

        best = None
        for p in plans:
            if p.is_best and p.plan_status == "draft":
                best = p
                break
        if not best:
            for p in plans:
                if p.plan_status == "draft":
                    best = p
                    break

        if best:
            from apps.api.app.planner_flow.service import approve_plan
            approval = approve_plan(s, best.id)
            check("Plan approved", approval["success"], approval.get("message", ""))
        else:
            check("Found draft plan to approve", False, "No draft plans found")
    except Exception as e:
        check("Plan approved", False, str(e))
    finally:
        s.close()

    # Verify transfers & reservations created
    s = SessionLocal()
    try:
        in_transit = s.query(DemoTransfer).filter(DemoTransfer.status == "in_transit").count()
        check(f"In-transit transfers created: {in_transit}", in_transit > 0)

        active_res = s.query(DemoReservation).filter(DemoReservation.status == "active").count()
        check(f"Active WH reservations created: {active_res}", active_res > 0)
    finally:
        s.close()


def step7_run_lorry_arrival():
    """Run simulate_lorry_arrival and verify results."""
    print("\n[Step 4] Running lorry arrival simulation...")
    s = SessionLocal()
    try:
        from scripts.simulate_lorry_arrival import simulate_lorry_arrival
        result = simulate_lorry_arrival(s)
        check("Lorry arrival executed", result["success"], result.get("message", ""))
        check(f"Transfers arrived: {result.get('arrived', 0)}", result.get("arrived", 0) > 0)
        return result
    except Exception as e:
        check("Lorry arrival executed", False, str(e))
        return {"success": False, "arrived": 0}
    finally:
        s.close()


def step8_verify_lorry_results():
    """Verify all transfers arrived, reservations released, events created."""
    s = SessionLocal()
    try:
        still_in_transit = s.query(DemoTransfer).filter(DemoTransfer.status == "in_transit").count()
        check("All transfers arrived (none still in_transit)", still_in_transit == 0,
             f"{still_in_transit} still in_transit")

        still_active = s.query(DemoReservation).filter(DemoReservation.status == "active").count()
        check("WH reservations released", still_active == 0,
             f"{still_active} still active")

        lorry_events = s.query(DemoArrivalEvent).filter(
            DemoArrivalEvent.event_type == "lorry_arrival"
        ).count()
        check(f"Lorry arrival events created: {lorry_events}", lorry_events > 0)
    finally:
        s.close()


def main():
    print("=" * 60)
    print("Phase C — Full End-to-End Verification")
    print("=" * 60)
    print()

    try:
        step1_reactivate_manifests()
        stock_before = step2_capture_wh_stock_before()
        step3_run_vessel_arrival()
        step4_verify_wh_stock_changed(stock_before)
        step5_verify_vessel_events()
        step5b_drain_dc_stock()
        step6_generate_and_approve_plan()
        step7_run_lorry_arrival()
        step8_verify_lorry_results()
    except Exception as e:
        print(f"\n  FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()

    print()
    print("=" * 60)
    total = Results.passed + Results.failed
    print(f"Results: {Results.passed}/{total} passed, {Results.failed} failed")
    if Results.failed == 0:
        print("PHASE C VERIFICATION PASSED")
    else:
        print("PHASE C VERIFICATION FAILED")
    print("=" * 60)
    sys.exit(0 if Results.failed == 0 else 1)


if __name__ == "__main__":
    main()
