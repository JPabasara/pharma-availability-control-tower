"""Seed all demo data from CSV files into the configured database.

Usage:
    python db/seeds/seed_all.py

This script is idempotent — it clears and reseeds on every run.
"""

import csv
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from apps.api.app.dependencies.database import SessionLocal
from storage.models import (
    Base,
    SKU,
    DC,
    Lorry,
    RouteEdge,
    Vessel,
    ManifestSnapshot,
    ManifestLine,
    WarehouseStockSnapshot,
    WarehouseStockItem,
    DCStockSnapshot,
    DCStockItem,
    SalesHistoryRecord,
    LorryStateSnapshot,
    LorryStateItem,
    ETASnapshot,
)

SEED_DIR = project_root / "data" / "seed"

# Reference time for demo: "now" in the demo world
DEMO_NOW = datetime(2026, 3, 30, 8, 0, 0, tzinfo=timezone.utc)


def read_csv(filename: str) -> list[dict]:
    """Read a CSV file from the seed directory."""
    filepath = SEED_DIR / filename
    with open(filepath, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def clear_all_tables(session):
    """Delete all data from all business tables (preserves schema)."""
<<<<<<< HEAD
    bind = session.get_bind()
    
    if bind.dialect.name == "postgresql":
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(text(f"TRUNCATE TABLE {table.name} CASCADE"))
    else:
        session.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.execute(text("SET FOREIGN_KEY_CHECKS = 1"))

=======
    for table in reversed(Base.metadata.sorted_tables):
        session.execute(table.delete())
>>>>>>> origin/main
    session.commit()
    print("  Cleared all tables.")


def seed_skus(session) -> int:
    """Seed SKU master data."""
    rows = read_csv("skus.csv")
    for row in rows:
        session.add(SKU(
            id=int(row["id"]),
            name=row["name"],
            code=row["code"],
            category=row["category"],
            reefer_required=bool(int(row["reefer_required"])),
            unit_weight_kg=float(row["unit_weight_kg"]),
            unit_volume_m3=float(row["unit_volume_m3"]),
        ))
    session.commit()
    print(f"  Seeded {len(rows)} SKUs.")
    return len(rows)


def seed_dcs(session) -> int:
    """Seed DC master data."""
    rows = read_csv("dcs.csv")
    for row in rows:
        session.add(DC(
            id=int(row["id"]),
            name=row["name"],
            code=row["code"],
            region=row["region"],
            latitude=float(row["latitude"]),
            longitude=float(row["longitude"]),
        ))
    session.commit()
    print(f"  Seeded {len(rows)} DCs.")
    return len(rows)


def seed_lorries(session) -> int:
    """Seed Lorry master data."""
    rows = read_csv("lorries.csv")
    for row in rows:
        session.add(Lorry(
            id=int(row["id"]),
            registration=row["registration"],
            lorry_type=row["lorry_type"],
            capacity_units=int(row["capacity_units"]),
            status=row["status"],
        ))
    session.commit()
    print(f"  Seeded {len(rows)} lorries.")
    return len(rows)


def seed_vessels(session) -> int:
    """Seed Vessel master data."""
    rows = read_csv("vessels.csv")
    for row in rows:
        session.add(Vessel(
            id=int(row["id"]),
            name=row["name"],
            code=row["code"],
            vessel_type=row["vessel_type"],
        ))
    session.commit()
    print(f"  Seeded {len(rows)} vessels.")
    return len(rows)


def seed_route_edges(session) -> int:
    """Seed fixed route graph edges."""
    rows = read_csv("route_edges.csv")
    for row in rows:
        session.add(RouteEdge(
            id=int(row["id"]),
            origin_type=row["origin_type"],
            origin_id=int(row["origin_id"]),
            destination_type=row["destination_type"],
            destination_id=int(row["destination_id"]),
            travel_time_hours=float(row["travel_time_hours"]),
            cost=float(row["cost"]),
        ))
    session.commit()
    print(f"  Seeded {len(rows)} route edges.")
    return len(rows)


def seed_warehouse_stock(session) -> int:
    """Seed initial warehouse stock snapshot."""
    rows = read_csv("warehouse_stock.csv")

    snapshot = WarehouseStockSnapshot(
        snapshot_time=DEMO_NOW - timedelta(hours=1),
    )
    session.add(snapshot)
    session.flush()

    for row in rows:
        physical = int(row["physical_quantity"])
        reserved = int(row["reserved_quantity"])
        session.add(WarehouseStockItem(
            snapshot_id=snapshot.id,
            sku_id=int(row["sku_id"]),
            physical_quantity=physical,
            reserved_quantity=reserved,
            effective_quantity=physical - reserved,
        ))

    session.commit()
    print(f"  Seeded warehouse stock snapshot with {len(rows)} items.")
    return len(rows)


def seed_dc_stock(session) -> int:
    """Seed initial DC stock snapshots (one per DC)."""
    rows = read_csv("dc_stock.csv")

    # Group by dc_id
    dc_rows: dict[int, list[dict]] = {}
    for row in rows:
        dc_id = int(row["dc_id"])
        dc_rows.setdefault(dc_id, []).append(row)

    total_items = 0
    for dc_id, items in sorted(dc_rows.items()):
        snapshot = DCStockSnapshot(
            dc_id=dc_id,
            snapshot_time=DEMO_NOW - timedelta(hours=1),
        )
        session.add(snapshot)
        session.flush()

        for row in items:
            physical = int(row["physical_quantity"])
            in_transit = int(row["in_transit_quantity"])
            session.add(DCStockItem(
                snapshot_id=snapshot.id,
                sku_id=int(row["sku_id"]),
                physical_quantity=physical,
                in_transit_quantity=in_transit,
                effective_quantity=physical + in_transit,
            ))
            total_items += 1

    session.commit()
    print(f"  Seeded {len(dc_rows)} DC stock snapshots with {total_items} total items.")
    return total_items


def seed_sales_history(session) -> int:
    """Seed 30 days of sales history by repeating the seeded weekly pattern."""
    rows = read_csv("sales_history.csv")
    total_rows = 0
    for row in rows:
        base_date = datetime.strptime(row["sale_date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        for offset_days in (0, 7, 14, 21):
            session.add(SalesHistoryRecord(
                dc_id=int(row["dc_id"]),
                sku_id=int(row["sku_id"]),
                sale_date=base_date - timedelta(days=offset_days),
                quantity_sold=int(row["quantity_sold"]),
            ))
            total_rows += 1
    session.commit()
    print(f"  Seeded {total_rows} sales history records.")
    return total_rows


def seed_manifests(session) -> int:
    """Seed 2 vessel manifest snapshots with lines."""
    total_lines = 0

    # Vessel 1 — arrives at DEMO_NOW + 6 hours
    manifest1 = ManifestSnapshot(
        manifest_name="Inbound Manifest Alpha",
        vessel_id=1,
        snapshot_time=DEMO_NOW - timedelta(hours=2),
        status="active",
    )
    session.add(manifest1)
    session.flush()

    rows1 = read_csv("manifest_vessel_1.csv")
    for row in rows1:
        session.add(ManifestLine(
            manifest_snapshot_id=manifest1.id,
            sku_id=int(row["sku_id"]),
            quantity=int(row["quantity"]),
            reefer_required=bool(int(row["reefer_required"])),
        ))
        total_lines += 1

    # Vessel 2 — arrives at DEMO_NOW + 24 hours (overlapping scenario)
    manifest2 = ManifestSnapshot(
        manifest_name="Inbound Manifest Beta",
        vessel_id=2,
        snapshot_time=DEMO_NOW - timedelta(hours=1),
        status="active",
    )
    session.add(manifest2)
    session.flush()

    rows2 = read_csv("manifest_vessel_2.csv")
    for row in rows2:
        session.add(ManifestLine(
            manifest_snapshot_id=manifest2.id,
            sku_id=int(row["sku_id"]),
            quantity=int(row["quantity"]),
            reefer_required=bool(int(row["reefer_required"])),
        ))
        total_lines += 1

    session.commit()
    print(f"  Seeded 2 manifest snapshots with {total_lines} total lines.")
    return total_lines


def seed_lorry_state(session) -> int:
    """Seed initial lorry state snapshot (all available)."""
    snapshot = LorryStateSnapshot(
        snapshot_time=DEMO_NOW - timedelta(hours=1),
    )
    session.add(snapshot)
    session.flush()

    rows = read_csv("lorries.csv")
    for row in rows:
        session.add(LorryStateItem(
            snapshot_id=snapshot.id,
            lorry_id=int(row["id"]),
            status="available",
        ))

    session.commit()
    print(f"  Seeded lorry state snapshot with {len(rows)} items (all available).")
    return len(rows)


def seed_eta_snapshots(session) -> int:
    """Seed ETA snapshots for both vessels."""
    # Vessel 1 ETA: DEMO_NOW + 6 hours
    session.add(ETASnapshot(
        vessel_id=1,
        eta_time=DEMO_NOW + timedelta(hours=6),
        fetched_at=DEMO_NOW - timedelta(hours=2),
        source="mock_api",
    ))

    # Vessel 2 ETA: DEMO_NOW + 24 hours (overlapping pressure)
    session.add(ETASnapshot(
        vessel_id=2,
        eta_time=DEMO_NOW + timedelta(hours=24),
        fetched_at=DEMO_NOW - timedelta(hours=1),
        source="mock_api",
    ))

    session.commit()
    print("  Seeded 2 ETA snapshots.")
    return 2


def main():
    """Run all seed operations."""
    print("=" * 60)
    print("Pharma Control Tower — Database Seed")
    print("=" * 60)
    print(f"Demo reference time: {DEMO_NOW.isoformat()}")
    print()

    session = SessionLocal()
    try:
        print("[1/9] Clearing existing data...")
        clear_all_tables(session)

        print("[2/9] Seeding SKUs...")
        seed_skus(session)

        print("[3/9] Seeding DCs...")
        seed_dcs(session)

        print("[4/9] Seeding lorries...")
        seed_lorries(session)

        print("[5/9] Seeding vessels...")
        seed_vessels(session)

        print("[6/9] Seeding route edges...")
        seed_route_edges(session)

        print("[7/9] Seeding warehouse & DC stock...")
        seed_warehouse_stock(session)
        seed_dc_stock(session)

        print("[8/9] Seeding sales history & manifests...")
        seed_sales_history(session)
        seed_manifests(session)

        print("[9/9] Seeding lorry state & ETA snapshots...")
        seed_lorry_state(session)
        seed_eta_snapshots(session)

        print()
        print("=" * 60)
        print("SEED COMPLETE")
        print("=" * 60)
        print()
        print("Demo scenarios encoded:")
        print("  1. Overlapping Vessels: VS-001 arrives +6h, VS-002 arrives +24h")
        print("  2. Urgent DC Shortage: DC-3 (Galle) near-zero stock + high sales")
        print("  3. Reefer Pressure: 5 reefer SKUs needing dispatch, only 3 reefer lorries")

    except Exception as e:
        session.rollback()
        print(f"\nERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
