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

from apps.api.app.dependencies.database import SessionLocal
from apps.api.app.demo_operations.service import arrive_open_stops


def simulate_lorry_arrival(
    session,
    dc_id: int | None = None,
    lorry_id: int | None = None,
) -> dict:
    """Process lorry arrivals through the shared demo-operations service."""
    return arrive_open_stops(session, dc_id=dc_id, lorry_id=lorry_id, actor="system_cli")


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
