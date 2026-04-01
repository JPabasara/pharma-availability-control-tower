"""Manifest snapshot reader — reads vessel manifests with line items and SKU metadata."""

from typing import Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session, joinedload

from storage.models import ManifestSnapshot, ManifestLine, SKU, Vessel


def get_latest(session: Session, vessel_id: Optional[int] = None) -> Optional[ManifestSnapshot]:
    """Fetch the most recent manifest snapshot, optionally filtered by vessel."""
    query = (
        session.query(ManifestSnapshot)
        .options(joinedload(ManifestSnapshot.lines))
        .filter(ManifestSnapshot.status == "active")
    )
    if vessel_id is not None:
        query = query.filter(ManifestSnapshot.vessel_id == vessel_id)
    return query.order_by(desc(ManifestSnapshot.snapshot_time)).first()


def get_all_active(session: Session) -> list[ManifestSnapshot]:
    """Fetch all active manifest snapshots."""
    return (
        session.query(ManifestSnapshot)
        .options(joinedload(ManifestSnapshot.lines))
        .filter(ManifestSnapshot.status == "active")
        .order_by(desc(ManifestSnapshot.snapshot_time))
        .all()
    )


def get_by_id(session: Session, snapshot_id: int) -> Optional[ManifestSnapshot]:
    """Fetch a specific manifest snapshot by ID."""
    return (
        session.query(ManifestSnapshot)
        .options(joinedload(ManifestSnapshot.lines))
        .filter(ManifestSnapshot.id == snapshot_id)
        .first()
    )


def to_contract(session: Session, snapshot: ManifestSnapshot) -> dict:
    """Normalize a manifest snapshot into an engine-ready contract dict.

    Returns:
        {
            manifest_snapshot_id: int,
            vessel_id: int,
            vessel_name: str,
            vessel_code: str,
            status: str,
            snapshot_time: str (ISO),
            lines: [
                {
                    manifest_line_id: int,
                    sku_id: int,
                    sku_code: str,
                    sku_name: str,
                    quantity: int,
                    reefer_required: bool
                }
            ]
        }
    """
    vessel = session.query(Vessel).filter(Vessel.id == snapshot.vessel_id).first()

    lines = []
    for line in snapshot.lines:
        sku = session.query(SKU).filter(SKU.id == line.sku_id).first()
        lines.append({
            "manifest_line_id": line.id,
            "sku_id": line.sku_id,
            "sku_code": sku.code if sku else "UNKNOWN",
            "sku_name": sku.name if sku else "Unknown SKU",
            "quantity": line.quantity,
            "reefer_required": line.reefer_required,
        })

    return {
        "manifest_snapshot_id": snapshot.id,
        "manifest_name": snapshot.manifest_name,
        "vessel_id": snapshot.vessel_id,
        "vessel_name": vessel.name if vessel else "Unknown Vessel",
        "vessel_code": vessel.code if vessel else "UNKNOWN",
        "status": snapshot.status,
        "snapshot_time": snapshot.snapshot_time.isoformat(),
        "lines": lines,
    }


def get_all_active_contracts(session: Session) -> list[dict]:
    """Get all active manifest snapshots as engine-ready contracts."""
    snapshots = get_all_active(session)
    return [to_contract(session, s) for s in snapshots]
