"""Simulate vessel arrival — converts manifest lines into physical warehouse stock.

Usage:
    python scripts/simulate_vessel_arrival.py                  # arrive ALL active vessels
    python scripts/simulate_vessel_arrival.py --vessel-id 1    # arrive a specific vessel

What it does:
    1. Finds active manifest snapshots (optionally filtered by vessel_id)
    2. For each manifest, increments physical warehouse stock for every SKU line
    3. Marks the manifest snapshot as 'arrived'
    4. Creates a demo_arrival_event record for auditability

This script is idempotent per manifest — already-arrived manifests are skipped.
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
    ManifestSnapshot,
    ManifestLine,
    Vessel,
    SKU,
    WarehouseStockSnapshot,
    WarehouseStockItem,
    DemoArrivalEvent,
    AuditLog,
)


def simulate_vessel_arrival(session, vessel_id: int | None = None) -> dict:
    """Process vessel arrivals and update warehouse stock.

    Returns summary dict with counts and details.
    """
    now = datetime.now(timezone.utc)

    # Find active manifests
    query = (
        session.query(ManifestSnapshot)
        .options(joinedload(ManifestSnapshot.lines))
        .filter(ManifestSnapshot.status == "active")
    )
    if vessel_id is not None:
        query = query.filter(ManifestSnapshot.vessel_id == vessel_id)

    manifests = query.order_by(ManifestSnapshot.snapshot_time).all()

    if not manifests:
        return {"success": True, "message": "No active manifests to process.", "arrived": 0}

    # Get the latest warehouse stock snapshot to update
    latest_wh = (
        session.query(WarehouseStockSnapshot)
        .options(joinedload(WarehouseStockSnapshot.items))
        .order_by(desc(WarehouseStockSnapshot.snapshot_time))
        .first()
    )

    if not latest_wh:
        return {"success": False, "message": "No warehouse stock snapshot found. Cannot update stock."}

    # Build a lookup of current WH stock items by SKU
    wh_items_by_sku: dict[int, WarehouseStockItem] = {
        item.sku_id: item for item in latest_wh.items
    }

    arrived_vessels = []
    total_skus_updated = 0
    total_quantity_added = 0

    for manifest in manifests:
        vessel = session.query(Vessel).filter(Vessel.id == manifest.vessel_id).first()
        vessel_name = vessel.name if vessel else f"Vessel #{manifest.vessel_id}"
        vessel_code = vessel.code if vessel else "UNKNOWN"

        manifest_details = []

        for line in manifest.lines:
            sku = session.query(SKU).filter(SKU.id == line.sku_id).first()
            sku_code = sku.code if sku else "UNKNOWN"

            if line.sku_id in wh_items_by_sku:
                # Increment existing WH stock
                wh_item = wh_items_by_sku[line.sku_id]
                old_qty = wh_item.physical_quantity
                wh_item.physical_quantity += line.quantity
                wh_item.effective_quantity = wh_item.physical_quantity - wh_item.reserved_quantity

                manifest_details.append({
                    "sku_id": line.sku_id,
                    "sku_code": sku_code,
                    "quantity_added": line.quantity,
                    "old_physical": old_qty,
                    "new_physical": wh_item.physical_quantity,
                })
            else:
                # Create new WH stock item for this SKU
                new_item = WarehouseStockItem(
                    snapshot_id=latest_wh.id,
                    sku_id=line.sku_id,
                    physical_quantity=line.quantity,
                    reserved_quantity=0,
                    effective_quantity=line.quantity,
                )
                session.add(new_item)
                wh_items_by_sku[line.sku_id] = new_item

                manifest_details.append({
                    "sku_id": line.sku_id,
                    "sku_code": sku_code,
                    "quantity_added": line.quantity,
                    "old_physical": 0,
                    "new_physical": line.quantity,
                })

            total_skus_updated += 1
            total_quantity_added += line.quantity

        # Mark manifest as arrived
        manifest.status = "arrived"

        # Create arrival event
        session.add(DemoArrivalEvent(
            event_type="vessel_arrival",
            reference_id=manifest.id,
            event_time=now,
            details={
                "vessel_id": manifest.vessel_id,
                "vessel_name": vessel_name,
                "vessel_code": vessel_code,
                "manifest_snapshot_id": manifest.id,
                "lines_processed": len(manifest.lines),
                "total_quantity": sum(d["quantity_added"] for d in manifest_details),
            },
        ))

        # Audit log
        session.add(AuditLog(
            entity_type="manifest_snapshot",
            entity_id=manifest.id,
            action="vessel_arrived",
            actor="system_cli",
            timestamp=now,
            details={
                "vessel_name": vessel_name,
                "skus_updated": len(manifest_details),
                "total_quantity_added": sum(d["quantity_added"] for d in manifest_details),
            },
        ))

        arrived_vessels.append({
            "vessel_id": manifest.vessel_id,
            "vessel_name": vessel_name,
            "vessel_code": vessel_code,
            "manifest_id": manifest.id,
            "lines_processed": len(manifest_details),
            "details": manifest_details,
        })

    session.commit()

    return {
        "success": True,
        "message": f"Processed {len(arrived_vessels)} vessel arrival(s).",
        "arrived": len(arrived_vessels),
        "total_skus_updated": total_skus_updated,
        "total_quantity_added": total_quantity_added,
        "vessels": arrived_vessels,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Simulate vessel arrival — increments physical warehouse stock from manifest lines."
    )
    parser.add_argument(
        "--vessel-id",
        type=int,
        default=None,
        help="Optional: Process only a specific vessel ID. Default: all active vessels.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would happen without committing to the database.",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("Pharma Control Tower — Simulate Vessel Arrival")
    print("=" * 60)
    if args.vessel_id:
        print(f"  Target vessel: {args.vessel_id}")
    else:
        print("  Target: all active vessels")
    if args.dry_run:
        print("  Mode: DRY RUN (no changes will be committed)")
    print()

    session = SessionLocal()
    try:
        result = simulate_vessel_arrival(session, vessel_id=args.vessel_id)

        if args.dry_run:
            session.rollback()
            print("  [DRY RUN] Changes rolled back.\n")

        if not result["success"]:
            print(f"  ERROR: {result['message']}")
            sys.exit(1)

        print(f"  {result['message']}")
        print()

        if result["arrived"] > 0:
            for v in result["vessels"]:
                print(f"  Vessel: {v['vessel_name']} ({v['vessel_code']})")
                print(f"    Manifest ID: {v['manifest_id']}")
                print(f"    Lines processed: {v['lines_processed']}")
                for d in v["details"]:
                    print(f"      {d['sku_code']}: +{d['quantity_added']} "
                          f"(was {d['old_physical']} → now {d['new_physical']})")
                print()

            print(f"  Total SKUs updated:   {result['total_skus_updated']}")
            print(f"  Total quantity added:  {result['total_quantity_added']}")
        else:
            print("  Nothing to process.")

        print()
        print("=" * 60)
        print("VESSEL ARRIVAL SIMULATION COMPLETE")
        print("=" * 60)

    except Exception as e:
        session.rollback()
        print(f"\nERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
