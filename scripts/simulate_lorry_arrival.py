"""Simulate lorry arrival — transfers in-transit goods to DC physical stock.

Usage:
    python scripts/simulate_lorry_arrival.py                    # arrive ALL in-transit transfers
    python scripts/simulate_lorry_arrival.py --dc-id 3          # arrive only transfers to DC 3
    python scripts/simulate_lorry_arrival.py --lorry-id 1       # arrive only transfers by lorry 1

What it does:
    1. Finds demo_transfers with status 'in_transit' (optionally filtered)
    2. For each transfer:
       a. Increments physical DC stock for each SKU
       b. Releases corresponding warehouse reservations (sets status='released')
       c. Marks the transfer as 'arrived' with arrived_at timestamp
    3. Creates demo_arrival_event records for auditability

This script is idempotent — already-arrived transfers are skipped (filtered by status).
"""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from sqlalchemy import desc
from sqlalchemy.orm import joinedload

from apps.api.app.dependencies.database import SessionLocal
from storage.models import (
    DemoTransfer,
    DemoReservation,
    DemoArrivalEvent,
    AuditLog,
    DCStockSnapshot,
    DCStockItem,
    SKU,
    DC,
    Lorry,
)


def simulate_lorry_arrival(
    session,
    dc_id: int | None = None,
    lorry_id: int | None = None,
) -> dict:
    """Process lorry arrivals: move stock from WH reservations to DC physical stock.

    Returns summary dict with counts and details.
    """
    now = datetime.now(timezone.utc)

    # Find in-transit transfers
    query = session.query(DemoTransfer).filter(DemoTransfer.status == "in_transit")
    if dc_id is not None:
        query = query.filter(DemoTransfer.dc_id == dc_id)
    if lorry_id is not None:
        query = query.filter(DemoTransfer.lorry_id == lorry_id)

    transfers = query.order_by(DemoTransfer.dispatched_at).all()

    if not transfers:
        return {"success": True, "message": "No in-transit transfers to process.", "arrived": 0}

    # Group transfers by DC for efficient stock updates
    dc_transfers: dict[int, list[DemoTransfer]] = {}
    for t in transfers:
        dc_transfers.setdefault(t.dc_id, []).append(t)

    # Track which plan_version + SKU reservations we've released
    released_reservations: set[tuple[int, int]] = set()

    arrived_details = []
    total_transfers = 0
    total_quantity_moved = 0
    total_reservations_released = 0

    for target_dc_id, dc_transfer_list in sorted(dc_transfers.items()):
        dc = session.query(DC).filter(DC.id == target_dc_id).first()
        dc_name = dc.name if dc else f"DC #{target_dc_id}"
        dc_code = dc.code if dc else "UNKNOWN"

        # Get latest DC stock snapshot for this DC
        latest_dc_snap = (
            session.query(DCStockSnapshot)
            .options(joinedload(DCStockSnapshot.items))
            .filter(DCStockSnapshot.dc_id == target_dc_id)
            .order_by(desc(DCStockSnapshot.snapshot_time))
            .first()
        )

        if not latest_dc_snap:
            # No existing snapshot — create one
            latest_dc_snap = DCStockSnapshot(
                dc_id=target_dc_id,
                snapshot_time=now,
            )
            session.add(latest_dc_snap)
            session.flush()

        # Build lookup of existing DC stock items by SKU
        dc_items_by_sku: dict[int, DCStockItem] = {
            item.sku_id: item for item in latest_dc_snap.items
        }

        dc_arrival_items = []

        for transfer in dc_transfer_list:
            sku = session.query(SKU).filter(SKU.id == transfer.sku_id).first()
            lorry = session.query(Lorry).filter(Lorry.id == transfer.lorry_id).first()
            sku_code = sku.code if sku else "UNKNOWN"
            registration = lorry.registration if lorry else "UNKNOWN"

            # Update DC physical stock
            if transfer.sku_id in dc_items_by_sku:
                dc_item = dc_items_by_sku[transfer.sku_id]
                old_qty = dc_item.physical_quantity
                dc_item.physical_quantity += transfer.quantity
                # Decrease in_transit since we're physically receiving
                dc_item.in_transit_quantity = max(0, dc_item.in_transit_quantity - transfer.quantity)
                dc_item.effective_quantity = dc_item.physical_quantity + dc_item.in_transit_quantity
            else:
                # Create new DC stock item
                dc_item = DCStockItem(
                    snapshot_id=latest_dc_snap.id,
                    sku_id=transfer.sku_id,
                    physical_quantity=transfer.quantity,
                    in_transit_quantity=0,
                    effective_quantity=transfer.quantity,
                )
                session.add(dc_item)
                dc_items_by_sku[transfer.sku_id] = dc_item
                old_qty = 0

            # Mark transfer as arrived
            transfer.status = "arrived"
            transfer.arrived_at = now

            # Release WH reservation for this plan + SKU (once per plan_version + sku combo)
            res_key = (transfer.plan_version_id, transfer.sku_id)
            if res_key not in released_reservations:
                reservations = (
                    session.query(DemoReservation)
                    .filter(
                        DemoReservation.plan_version_id == transfer.plan_version_id,
                        DemoReservation.sku_id == transfer.sku_id,
                        DemoReservation.status == "active",
                    )
                    .all()
                )
                for res in reservations:
                    res.status = "released"
                    total_reservations_released += 1
                released_reservations.add(res_key)

            dc_arrival_items.append({
                "transfer_id": transfer.id,
                "lorry_id": transfer.lorry_id,
                "registration": registration,
                "sku_id": transfer.sku_id,
                "sku_code": sku_code,
                "quantity": transfer.quantity,
                "old_dc_physical": old_qty,
                "new_dc_physical": old_qty + transfer.quantity,
            })

            total_transfers += 1
            total_quantity_moved += transfer.quantity

        # Create arrival event for this DC batch
        session.add(DemoArrivalEvent(
            event_type="lorry_arrival",
            reference_id=target_dc_id,
            event_time=now,
            details={
                "dc_id": target_dc_id,
                "dc_name": dc_name,
                "dc_code": dc_code,
                "transfers_processed": len(dc_arrival_items),
                "total_quantity": sum(i["quantity"] for i in dc_arrival_items),
                "lorry_ids": list(set(i["lorry_id"] for i in dc_arrival_items)),
            },
        ))

        # Audit log
        session.add(AuditLog(
            entity_type="demo_transfer",
            entity_id=target_dc_id,
            action="lorry_arrived",
            actor="system_cli",
            timestamp=now,
            details={
                "dc_name": dc_name,
                "transfers_count": len(dc_arrival_items),
                "total_quantity": sum(i["quantity"] for i in dc_arrival_items),
                "reservations_released": total_reservations_released,
            },
        ))

        arrived_details.append({
            "dc_id": target_dc_id,
            "dc_name": dc_name,
            "dc_code": dc_code,
            "transfers": dc_arrival_items,
        })

    session.commit()

    return {
        "success": True,
        "message": f"Processed {total_transfers} lorry arrival(s) across {len(arrived_details)} DC(s).",
        "arrived": total_transfers,
        "total_quantity_moved": total_quantity_moved,
        "total_reservations_released": total_reservations_released,
        "dcs": arrived_details,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Simulate lorry arrival — transfers in-transit goods to DC physical stock."
    )
    parser.add_argument(
        "--dc-id",
        type=int,
        default=None,
        help="Optional: Process only transfers to a specific DC ID.",
    )
    parser.add_argument(
        "--lorry-id",
        type=int,
        default=None,
        help="Optional: Process only transfers by a specific lorry ID.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would happen without committing to the database.",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("Pharma Control Tower — Simulate Lorry Arrival")
    print("=" * 60)
    if args.dc_id:
        print(f"  Target DC: {args.dc_id}")
    if args.lorry_id:
        print(f"  Target lorry: {args.lorry_id}")
    if not args.dc_id and not args.lorry_id:
        print("  Target: all in-transit transfers")
    if args.dry_run:
        print("  Mode: DRY RUN (no changes will be committed)")
    print()

    session = SessionLocal()
    try:
        result = simulate_lorry_arrival(session, dc_id=args.dc_id, lorry_id=args.lorry_id)

        if args.dry_run:
            session.rollback()
            print("  [DRY RUN] Changes rolled back.\n")

        if not result["success"]:
            print(f"  ERROR: {result['message']}")
            sys.exit(1)

        print(f"  {result['message']}")
        print()

        if result["arrived"] > 0:
            for dc_info in result["dcs"]:
                print(f"  DC: {dc_info['dc_name']} ({dc_info['dc_code']})")
                for t in dc_info["transfers"]:
                    print(f"    Lorry {t['registration']} → {t['sku_code']}: "
                          f"+{t['quantity']} (was {t['old_dc_physical']} → now {t['new_dc_physical']})")
                print()

            print(f"  Total transfers arrived:      {result['arrived']}")
            print(f"  Total quantity moved to DCs:   {result['total_quantity_moved']}")
            print(f"  WH reservations released:      {result['total_reservations_released']}")
        else:
            print("  Nothing to process.")

        print()
        print("=" * 60)
        print("LORRY ARRIVAL SIMULATION COMPLETE")
        print("=" * 60)

    except Exception as e:
        session.rollback()
        print(f"\nERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
