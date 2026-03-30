"""Lorry state reader — reads lorry availability from latest snapshot joined with lorry master data."""

from typing import Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session, joinedload

from storage.models import LorryStateSnapshot, LorryStateItem, Lorry


def get_latest(session: Session) -> Optional[LorryStateSnapshot]:
    """Fetch the most recent lorry state snapshot."""
    return (
        session.query(LorryStateSnapshot)
        .options(joinedload(LorryStateSnapshot.items))
        .order_by(desc(LorryStateSnapshot.snapshot_time))
        .first()
    )


def get_by_id(session: Session, snapshot_id: int) -> Optional[LorryStateSnapshot]:
    """Fetch a specific lorry state snapshot by ID."""
    return (
        session.query(LorryStateSnapshot)
        .options(joinedload(LorryStateSnapshot.items))
        .filter(LorryStateSnapshot.id == snapshot_id)
        .first()
    )


def to_contract(session: Session, snapshot: LorryStateSnapshot) -> dict:
    """Normalize lorry state into an engine-ready contract.

    Returns:
        {
            snapshot_id: int,
            snapshot_time: str (ISO),
            lorries: [
                {
                    lorry_id: int,
                    registration: str,
                    lorry_type: str (normal|reefer),
                    capacity_units: int,
                    status: str (available|unavailable)
                }
            ]
        }
    """
    lorries = []
    for item in snapshot.items:
        lorry = session.query(Lorry).filter(Lorry.id == item.lorry_id).first()
        if lorry:
            lorries.append({
                "lorry_id": lorry.id,
                "registration": lorry.registration,
                "lorry_type": lorry.lorry_type,
                "capacity_units": lorry.capacity_units,
                "status": item.status,
            })

    return {
        "snapshot_id": snapshot.id,
        "snapshot_time": snapshot.snapshot_time.isoformat(),
        "lorries": lorries,
    }


def get_latest_contract(session: Session) -> Optional[dict]:
    """Get latest lorry state as an engine-ready contract."""
    snapshot = get_latest(session)
    if snapshot is None:
        return None
    return to_contract(session, snapshot)


def get_available_lorries(session: Session) -> list[dict]:
    """Get only available lorries from the latest snapshot."""
    contract = get_latest_contract(session)
    if contract is None:
        return []
    return [l for l in contract["lorries"] if l["status"] == "available"]
