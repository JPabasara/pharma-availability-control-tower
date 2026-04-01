"""Demo State Service — manages reservations, transfers, and stock projections.

Provides read access to the demo-state tables for the frontend and reporting.
"""

from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from storage.models import (
    DemoReservation,
    DemoTransfer,
    DemoArrivalEvent,
    SKU,
    DC,
    Lorry,
    M3PlanStop,
)
from integrations.inbound.warehouse_stock_reader import reader as wh_reader
from integrations.inbound.dc_stock_reader import reader as dc_reader


def get_reservations(
    session: Session,
    plan_version_id: Optional[int] = None,
    status: Optional[str] = None,
) -> list[dict]:
    """List demo reservations, optionally filtered by plan or status.

    Returns:
        [{id, plan_version_id, sku_id, sku_code, quantity_reserved, status, created_at}]
    """
    query = session.query(DemoReservation)

    if plan_version_id is not None:
        query = query.filter(DemoReservation.plan_version_id == plan_version_id)
    if status is not None:
        query = query.filter(DemoReservation.status == status)

    reservations = query.order_by(DemoReservation.created_at.desc()).all()

    result = []
    for r in reservations:
        sku = session.query(SKU).filter(SKU.id == r.sku_id).first()
        result.append({
            "id": r.id,
            "plan_version_id": r.plan_version_id,
            "plan_stop_id": r.plan_stop_id,
            "sku_id": r.sku_id,
            "sku_code": sku.code if sku else "UNKNOWN",
            "sku_name": sku.name if sku else "Unknown",
            "quantity_reserved": r.quantity_reserved,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })

    return result


def get_transfers(
    session: Session,
    status: Optional[str] = None,
) -> list[dict]:
    """List demo transfers, optionally filtered by status.

    Returns:
        [{id, plan_version_id, lorry_id, registration, dc_id, dc_code, sku_id, sku_code,
          quantity, status, dispatched_at, arrived_at}]
    """
    query = session.query(DemoTransfer)

    if status is not None:
        query = query.filter(DemoTransfer.status == status)

    transfers = query.order_by(DemoTransfer.created_at.desc()).all()

    result = []
    for t in transfers:
        sku = session.query(SKU).filter(SKU.id == t.sku_id).first()
        dc = session.query(DC).filter(DC.id == t.dc_id).first()
        lorry = session.query(Lorry).filter(Lorry.id == t.lorry_id).first()
        stop = session.query(M3PlanStop).filter(M3PlanStop.id == t.plan_stop_id).first() if t.plan_stop_id else None

        result.append({
            "id": t.id,
            "plan_version_id": t.plan_version_id,
            "plan_stop_id": t.plan_stop_id,
            "lorry_id": t.lorry_id,
            "registration": lorry.registration if lorry else "UNKNOWN",
            "lorry_type": lorry.lorry_type if lorry else "unknown",
            "dc_id": t.dc_id,
            "dc_code": dc.code if dc else "UNKNOWN",
            "dc_name": dc.name if dc else "Unknown",
            "sku_id": t.sku_id,
            "sku_code": sku.code if sku else "UNKNOWN",
            "sku_name": sku.name if sku else "Unknown",
            "quantity": t.quantity,
            "dispatch_day": stop.dispatch_day if stop else None,
            "stop_sequence": stop.stop_sequence if stop else None,
            "status": t.status,
            "dispatched_at": t.dispatched_at.isoformat() if t.dispatched_at else None,
            "arrived_at": t.arrived_at.isoformat() if t.arrived_at else None,
        })

    return result


def get_stock_summary(session: Session) -> dict:
    """Get aggregated stock summary across warehouse and all DCs.

    Returns:
        {
            warehouse: {items: [{sku_id, sku_code, physical, reserved, effective}]},
            dcs: [{dc_id, dc_code, items: [{sku_id, sku_code, physical, in_transit, effective}]}],
            totals: {
                total_wh_physical: int,
                total_wh_reserved: int,
                total_wh_effective: int,
                total_dc_physical: int,
                total_dc_in_transit: int,
                total_dc_effective: int,
            }
        }
    """
    wh_contract = wh_reader.get_latest_contract(session)
    dc_contracts = dc_reader.get_all_latest_contracts(session)

    # Compute totals
    wh_physical = sum(i["physical"] for i in wh_contract["items"]) if wh_contract else 0
    wh_reserved = sum(i["reserved"] for i in wh_contract["items"]) if wh_contract else 0
    wh_effective = sum(i["effective"] for i in wh_contract["items"]) if wh_contract else 0

    dc_physical = sum(
        sum(i["physical"] for i in dc["items"])
        for dc in dc_contracts
    )
    dc_in_transit = sum(
        sum(i["in_transit"] for i in dc["items"])
        for dc in dc_contracts
    )
    dc_effective = sum(
        sum(i["effective"] for i in dc["items"])
        for dc in dc_contracts
    )

    return {
        "warehouse": wh_contract or {"items": []},
        "dcs": dc_contracts,
        "totals": {
            "total_wh_physical": wh_physical,
            "total_wh_reserved": wh_reserved,
            "total_wh_effective": wh_effective,
            "total_dc_physical": dc_physical,
            "total_dc_in_transit": dc_in_transit,
            "total_dc_effective": dc_effective,
        },
    }


def get_arrival_events(session: Session, event_type: Optional[str] = None) -> list[dict]:
    """List demo arrival events.

    Returns:
        [{id, event_type, reference_id, event_time, details}]
    """
    query = session.query(DemoArrivalEvent)
    if event_type:
        query = query.filter(DemoArrivalEvent.event_type == event_type)

    events = query.order_by(DemoArrivalEvent.event_time.desc()).all()

    return [
        {
            "id": e.id,
            "event_type": e.event_type,
            "reference_id": e.reference_id,
            "event_time": e.event_time.isoformat() if e.event_time else None,
            "details": e.details,
        }
        for e in events
    ]
