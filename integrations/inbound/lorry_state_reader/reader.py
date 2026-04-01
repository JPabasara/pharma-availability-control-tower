"""Lorry state reader — exposes the current 2-day effective lorry horizon."""

from typing import Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session, joinedload

from apps.api.app.dependencies.business_time import get_planning_dates
from storage.models import DemoLorryDayState, LorryStateSnapshot, LorryStateItem, Lorry


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
    """Normalize lorry state into a 2-day engine-ready contract.

    Returns:
        {
            snapshot_id: int,
            snapshot_time: str (ISO),
            planning_dates: [str, str],
            lorries: [
                {
                    lorry_id: int,
                    registration: str,
                    lorry_type: str (normal|reefer),
                    capacity_units: int,
                    status: str (base snapshot status),
                    day1_status: str,
                    day2_status: str,
                    day_states: [{dispatch_day, business_date, status, source}]
                }
            ]
        }
    """
    planning_dates = get_planning_dates()
    override_rows = (
        session.query(DemoLorryDayState)
        .filter(DemoLorryDayState.business_date.in_(planning_dates))
        .all()
    )
    overrides = {(row.lorry_id, row.business_date): row for row in override_rows}

    lorries = []
    for item in snapshot.items:
        lorry = session.query(Lorry).filter(Lorry.id == item.lorry_id).first()
        if lorry:
            day_states = []
            for dispatch_day, business_date in enumerate(planning_dates, start=1):
                override = overrides.get((lorry.id, business_date))
                day_states.append({
                    "dispatch_day": dispatch_day,
                    "business_date": business_date.isoformat(),
                    "status": override.status if override else item.status,
                    "source": override.source if override else "snapshot",
                })

            lorries.append({
                "lorry_id": lorry.id,
                "registration": lorry.registration,
                "lorry_type": lorry.lorry_type,
                "capacity_units": lorry.capacity_units,
                "status": item.status,
                "day1_status": day_states[0]["status"],
                "day2_status": day_states[1]["status"],
                "day_states": day_states,
            })

    return {
        "snapshot_id": snapshot.id,
        "snapshot_time": snapshot.snapshot_time.isoformat(),
        "planning_dates": [value.isoformat() for value in planning_dates],
        "lorries": lorries,
    }


def get_latest_contract(session: Session) -> Optional[dict]:
    """Get latest lorry state as an engine-ready contract."""
    snapshot = get_latest(session)
    if snapshot is None:
        return None
    return to_contract(session, snapshot)


def get_available_lorries(session: Session) -> list[dict]:
    """Get only lorries with at least one available day in the current horizon."""
    contract = get_latest_contract(session)
    if contract is None:
        return []
    return [
        lorry
        for lorry in contract["lorries"]
        if lorry["day1_status"] == "available" or lorry["day2_status"] == "available"
    ]
