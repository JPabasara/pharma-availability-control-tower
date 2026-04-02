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


def get_active_vessel_ids(session: Session) -> list[int]:
    """Return vessel ids that currently have active manifests."""
    active_vessels = (
        session.query(ManifestSnapshot.vessel_id)
        .filter(ManifestSnapshot.status == "active")
        .distinct()
        .all()
    )
    return [value[0] for value in active_vessels]


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
    vessel_ids = get_active_vessel_ids(session)

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


def refresh_eta(session: Session, vessel_id: int, *, auto_commit: bool = True) -> dict:
    """Generate a new mock ETA for a vessel and persist it.

    Mock logic:
    - If a previous ETA exists, there's an 80% chance of a minor drift (-3 to +3 hours)
      and a 20% chance of a major delay (+6 to +18 hours).
    - If no previous ETA exists, generates a fresh random offset (12-48 hours).
    """
    now = datetime.now(timezone.utc)
    latest = get_latest_eta(session, vessel_id)

    if latest:
        if random.random() < 0.80:
            offset_hours = random.uniform(-3.0, 3.0)
        else:
            offset_hours = random.uniform(6.0, 18.0)
            
        old_eta = latest.eta_time
        if old_eta.tzinfo is None:
            old_eta = old_eta.replace(tzinfo=timezone.utc)
            
        new_eta_time = old_eta + timedelta(hours=offset_hours)
        
        # Prevent ETA from shifting into the past if the vessel hasn't arrived
        if new_eta_time < now:
            new_eta_time = now + timedelta(hours=random.uniform(1.0, 4.0))
            
        hours_until_arrival = (new_eta_time - now).total_seconds() / 3600.0
    else:
        offset_hours = random.uniform(12.0, 48.0)
        new_eta_time = now + timedelta(hours=offset_hours)
        hours_until_arrival = offset_hours

    eta_snapshot = ETASnapshot(
        vessel_id=vessel_id,
        eta_time=new_eta_time,
        fetched_at=now,
        source="mock_api",
    )
    session.add(eta_snapshot)
    if auto_commit:
        session.commit()
    else:
        session.flush()

    vessel = session.query(Vessel).filter(Vessel.id == vessel_id).first()

    return {
        "vessel_id": vessel_id,
        "vessel_name": vessel.name if vessel else "Unknown",
        "vessel_code": vessel.code if vessel else "UNKNOWN",
        "eta_time": new_eta_time.isoformat(),
        "fetched_at": now.isoformat(),
        "hours_until_arrival": round(hours_until_arrival, 1),
        "source": "mock_api",
    }


def refresh_all_active_etas(session: Session, *, auto_commit: bool = True) -> dict:
    """Create fresh ETA snapshots for all vessels with active manifests."""
    vessel_ids = get_active_vessel_ids(session)
    records = [refresh_eta(session, vessel_id, auto_commit=False) for vessel_id in vessel_ids]
    if auto_commit:
        session.commit()
    return {
        "count": len(records),
        "etas": records,
        "latest_fetched_at": max((record["fetched_at"] for record in records), default=None),
    }


def to_contract(session: Session) -> list[dict]:
    """Return all active ETAs as the engine-ready contract."""
    return get_all_active_etas(session)
