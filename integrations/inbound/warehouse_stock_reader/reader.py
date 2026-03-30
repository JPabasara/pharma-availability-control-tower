"""Warehouse stock reader — computes Effective = Physical − Reserved (from active demo_reservations)."""

from typing import Optional

from sqlalchemy import desc, func
from sqlalchemy.orm import Session, joinedload

from storage.models import (
    WarehouseStockSnapshot,
    WarehouseStockItem,
    SKU,
    DemoReservation,
)


def get_latest(session: Session) -> Optional[WarehouseStockSnapshot]:
    """Fetch the most recent warehouse stock snapshot."""
    return (
        session.query(WarehouseStockSnapshot)
        .options(joinedload(WarehouseStockSnapshot.items))
        .order_by(desc(WarehouseStockSnapshot.snapshot_time))
        .first()
    )


def get_by_id(session: Session, snapshot_id: int) -> Optional[WarehouseStockSnapshot]:
    """Fetch a specific warehouse stock snapshot by ID."""
    return (
        session.query(WarehouseStockSnapshot)
        .options(joinedload(WarehouseStockSnapshot.items))
        .filter(WarehouseStockSnapshot.id == snapshot_id)
        .first()
    )


def _compute_live_reserved(session: Session) -> dict[int, int]:
    """Sum active demo_reservations per SKU to get live reserved quantities.

    This ensures "Effective Stock" is always accurate even after plan approvals.
    """
    rows = (
        session.query(
            DemoReservation.sku_id,
            func.coalesce(func.sum(DemoReservation.quantity_reserved), 0).label("total_reserved"),
        )
        .filter(DemoReservation.status == "active")
        .group_by(DemoReservation.sku_id)
        .all()
    )
    return {row.sku_id: int(row.total_reserved) for row in rows}


def to_contract(session: Session, snapshot: WarehouseStockSnapshot) -> dict:
    """Normalize warehouse stock into an engine-ready contract with live Effective calculation.

    Effective = Physical − live_reserved (summed from active demo_reservations)

    Returns:
        {
            snapshot_id: int,
            snapshot_time: str (ISO),
            items: [
                {
                    sku_id: int,
                    sku_code: str,
                    sku_name: str,
                    reefer_required: bool,
                    physical: int,
                    reserved: int,
                    effective: int
                }
            ]
        }
    """
    live_reserved = _compute_live_reserved(session)

    items = []
    for item in snapshot.items:
        sku = session.query(SKU).filter(SKU.id == item.sku_id).first()
        reserved = live_reserved.get(item.sku_id, 0)
        effective = item.physical_quantity - reserved

        items.append({
            "sku_id": item.sku_id,
            "sku_code": sku.code if sku else "UNKNOWN",
            "sku_name": sku.name if sku else "Unknown SKU",
            "reefer_required": sku.reefer_required if sku else False,
            "physical": item.physical_quantity,
            "reserved": reserved,
            "effective": max(effective, 0),
        })

    return {
        "snapshot_id": snapshot.id,
        "snapshot_time": snapshot.snapshot_time.isoformat(),
        "items": items,
    }


def get_latest_contract(session: Session) -> Optional[dict]:
    """Get latest warehouse stock as an engine-ready contract."""
    snapshot = get_latest(session)
    if snapshot is None:
        return None
    return to_contract(session, snapshot)
