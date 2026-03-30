"""Demo state endpoints — reservations, transfers, stock summary, and arrival events.

Routes:
    GET /api/v1/demo-state/reservations      — active/all reservations
    GET /api/v1/demo-state/transfers          — transfers by status
    GET /api/v1/demo-state/stock-summary      — aggregated effective stock view
    GET /api/v1/demo-state/arrival-events     — arrival event log
"""

from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.api.app.dependencies.database import get_db
from demo_state import services as demo_service

router = APIRouter(prefix="/api/v1/demo-state", tags=["demo-state"])


@router.get("/reservations")
def get_reservations(
    plan_version_id: Optional[int] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """List demo reservations (WH side), optionally filtered by plan or status."""
    reservations = demo_service.get_reservations(db, plan_version_id=plan_version_id, status=status)
    return {"reservations": reservations, "count": len(reservations)}


@router.get("/transfers")
def get_transfers(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """List demo transfers (DC side), optionally filtered by status (in_transit|arrived)."""
    transfers = demo_service.get_transfers(db, status=status)
    return {"transfers": transfers, "count": len(transfers)}


@router.get("/stock-summary")
def get_stock_summary(db: Session = Depends(get_db)):
    """Get aggregated stock summary across warehouse and all DCs.

    Shows physical, reserved/in-transit, and effective quantities.
    """
    return demo_service.get_stock_summary(db)


@router.get("/arrival-events")
def get_arrival_events(
    event_type: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """List demo arrival events (vessel_arrival, lorry_arrival)."""
    events = demo_service.get_arrival_events(db, event_type=event_type)
    return {"events": events, "count": len(events)}
