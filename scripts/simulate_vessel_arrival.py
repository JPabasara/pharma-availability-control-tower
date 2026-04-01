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

from apps.api.app.dependencies.database import SessionLocal
from apps.api.app.demo_operations.service import arrive_active_manifests


def simulate_vessel_arrival(session, vessel_id: int | None = None) -> dict:
    """Process vessel arrivals through the shared demo-operations service."""
    return arrive_active_manifests(session, vessel_id=vessel_id, actor="system_cli")


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
