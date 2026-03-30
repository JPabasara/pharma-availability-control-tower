"""ETA mock provider — generates and persists mock vessel ETAs."""

import random
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from storage.models import ETASnapshot, Vessel, ManifestSnapshot


def get_latest_eta(session: Session, vessel_id: int) -> Optional[ETASnapshot]:
    """Get the most recent ETA snapshot for a specific vessel."""
    return (
        session.query(ETASnapshot)
        .filter(ETASnapshot.vessel_id == vessel_id)
        .order_by(desc(ETASnapshot.fetched_at))
        .first()
    )


def get_all_active_etas(session: Session) -> list[dict]:
    """Get latest ETAs for all vessels that have active manifests.

    Returns:
        [
            {
                vessel_id: int,
                vessel_name: str,
                vessel_code: str,
                eta_time: str (ISO),
                fetched_at: str (ISO),
                hours_until_arrival: float,
                source: str
            }
        ]
    """
    # Find vessels with active manifests
    active_vessels = (
        session.query(ManifestSnapshot.vessel_id)
        .filter(ManifestSnapshot.status == "active")
        .distinct()
        .all()
    )
    vessel_ids = [v[0] for v in active_vessels]

    etas = []
    now = datetime.now(timezone.utc)

    for vid in vessel_ids:
        eta_snap = get_latest_eta(session, vid)
        vessel = session.query(Vessel).filter(Vessel.id == vid).first()

        if eta_snap and vessel:
            # MySQL may return naive datetimes — normalize for safe comparison
            eta_time = eta_snap.eta_time
            if eta_time.tzinfo is None:
                eta_time = eta_time.replace(tzinfo=timezone.utc)
            hours_until = max(0, (eta_time - now).total_seconds() / 3600)
            etas.append({
                "vessel_id": vid,
                "vessel_name": vessel.name,
                "vessel_code": vessel.code,
                "eta_time": eta_time.isoformat(),
                "fetched_at": eta_snap.fetched_at.isoformat(),
                "hours_until_arrival": round(hours_until, 1),
                "source": eta_snap.source,
            })

    return etas


def refresh_eta(session: Session, vessel_id: int) -> dict:
    """Generate a new mock ETA for a vessel and persist it.

    Mock logic: current time + random offset between 4-48 hours.
    Each refresh simulates an updated ETA from a real tracking API.

    Returns the newly created ETA as a dict.
    """
    now = datetime.now(timezone.utc)
    offset_hours = random.uniform(4, 48)
    new_eta_time = now + timedelta(hours=offset_hours)

    eta_snapshot = ETASnapshot(
        vessel_id=vessel_id,
        eta_time=new_eta_time,
        fetched_at=now,
        source="mock_api",
    )
    session.add(eta_snapshot)
    session.commit()

    vessel = session.query(Vessel).filter(Vessel.id == vessel_id).first()

    return {
        "vessel_id": vessel_id,
        "vessel_name": vessel.name if vessel else "Unknown",
        "vessel_code": vessel.code if vessel else "UNKNOWN",
        "eta_time": new_eta_time.isoformat(),
        "fetched_at": now.isoformat(),
        "hours_until_arrival": round(offset_hours, 1),
        "source": "mock_api",
    }


def to_contract(session: Session) -> list[dict]:
    """Return all active ETAs as the engine-ready contract."""
    return get_all_active_etas(session)
