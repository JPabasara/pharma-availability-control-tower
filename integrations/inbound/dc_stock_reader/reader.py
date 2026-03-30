"""DC stock reader — computes Effective = Physical + In-Transit (from active demo_transfers)."""

from typing import Optional

from sqlalchemy import desc, func
from sqlalchemy.orm import Session, joinedload

from storage.models import (
    DCStockSnapshot,
    DCStockItem,
    DC,
    SKU,
    DemoTransfer,
)


def get_latest(session: Session, dc_id: Optional[int] = None) -> list[DCStockSnapshot]:
    """Fetch the most recent DC stock snapshots.

    If dc_id is provided, returns a list of one snapshot for that DC.
    Otherwise, returns the latest snapshot for each DC.
    """
    if dc_id is not None:
        snap = (
            session.query(DCStockSnapshot)
            .options(joinedload(DCStockSnapshot.items))
            .filter(DCStockSnapshot.dc_id == dc_id)
            .order_by(desc(DCStockSnapshot.snapshot_time))
            .first()
        )
        return [snap] if snap else []

    # Latest snapshot per DC — get all DCs, then latest for each
    dcs = session.query(DC).all()
    snapshots = []
    for dc in dcs:
        snap = (
            session.query(DCStockSnapshot)
            .options(joinedload(DCStockSnapshot.items))
            .filter(DCStockSnapshot.dc_id == dc.id)
            .order_by(desc(DCStockSnapshot.snapshot_time))
            .first()
        )
        if snap:
            snapshots.append(snap)
    return snapshots


def get_by_id(session: Session, snapshot_id: int) -> Optional[DCStockSnapshot]:
    """Fetch a specific DC stock snapshot by ID."""
    return (
        session.query(DCStockSnapshot)
        .options(joinedload(DCStockSnapshot.items))
        .filter(DCStockSnapshot.id == snapshot_id)
        .first()
    )


def _compute_live_in_transit(session: Session) -> dict[tuple[int, int], int]:
    """Sum active demo_transfers per (dc_id, sku_id) to get live in-transit quantities.

    Only counts transfers with status 'in_transit'.
    """
    rows = (
        session.query(
            DemoTransfer.dc_id,
            DemoTransfer.sku_id,
            func.coalesce(func.sum(DemoTransfer.quantity), 0).label("total_in_transit"),
        )
        .filter(DemoTransfer.status == "in_transit")
        .group_by(DemoTransfer.dc_id, DemoTransfer.sku_id)
        .all()
    )
    return {(row.dc_id, row.sku_id): int(row.total_in_transit) for row in rows}


def to_contract(session: Session, snapshot: DCStockSnapshot) -> dict:
    """Normalize DC stock snapshot into an engine-ready contract.

    Effective = Physical + live_in_transit (summed from in_transit demo_transfers)

    Returns:
        {
            dc_id: int,
            dc_code: str,
            dc_name: str,
            snapshot_id: int,
            snapshot_time: str (ISO),
            items: [
                {
                    sku_id: int,
                    sku_code: str,
                    sku_name: str,
                    physical: int,
                    in_transit: int,
                    effective: int
                }
            ]
        }
    """
    dc = session.query(DC).filter(DC.id == snapshot.dc_id).first()
    live_in_transit = _compute_live_in_transit(session)

    items = []
    for item in snapshot.items:
        sku = session.query(SKU).filter(SKU.id == item.sku_id).first()
        in_transit = live_in_transit.get((snapshot.dc_id, item.sku_id), 0)
        effective = item.physical_quantity + in_transit

        items.append({
            "sku_id": item.sku_id,
            "sku_code": sku.code if sku else "UNKNOWN",
            "sku_name": sku.name if sku else "Unknown SKU",
            "physical": item.physical_quantity,
            "in_transit": in_transit,
            "effective": effective,
        })

    return {
        "dc_id": snapshot.dc_id,
        "dc_code": dc.code if dc else "UNKNOWN",
        "dc_name": dc.name if dc else "Unknown DC",
        "snapshot_id": snapshot.id,
        "snapshot_time": snapshot.snapshot_time.isoformat(),
        "items": items,
    }


def get_all_latest_contracts(session: Session) -> list[dict]:
    """Get latest DC stock for all DCs as engine-ready contracts."""
    snapshots = get_latest(session)
    return [to_contract(session, s) for s in snapshots]


def get_dc_contract(session: Session, dc_id: int) -> Optional[dict]:
    """Get latest DC stock for a specific DC as an engine-ready contract."""
    snapshots = get_latest(session, dc_id=dc_id)
    if not snapshots:
        return None
    return to_contract(session, snapshots[0])
