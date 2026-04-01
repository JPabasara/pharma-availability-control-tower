"""Reporting endpoints — approved plan views and audit trail.

Routes:
    GET /api/v1/reports/approved-plans    — all approved plans with full detail
    GET /api/v1/reports/audit-trail       — audit log entries
"""

from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload

from apps.api.app.dependencies.database import get_db
from storage.models import (
    M3PlanRun,
    M3PlanVersion,
    M3PlanStop,
    M3PlanItem,
    PlannerDecision,
    OverrideReason,
    AuditLog,
    SKU,
    DC,
    Lorry,
)

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


@router.get("/approved-plans")
def get_approved_plans(db: Session = Depends(get_db)):
    """Get all approved plans with their stop and item details."""
    plans = (
        db.query(M3PlanVersion)
        .options(
            joinedload(M3PlanVersion.runs)
            .joinedload(M3PlanRun.stops)
            .joinedload(M3PlanStop.items)
        )
        .filter(M3PlanVersion.plan_status == "approved")
        .order_by(M3PlanVersion.approved_at.desc())
        .all()
    )

    result = []
    for plan in plans:
        # Get associated decisions
        decisions = (
            db.query(PlannerDecision)
            .filter(PlannerDecision.plan_version_id == plan.id)
            .order_by(PlannerDecision.decided_at)
            .all()
        )

        decision_list = []
        for d in decisions:
            decision_data = {
                "id": d.id,
                "decision_type": d.decision_type,
                "decided_at": d.decided_at.isoformat() if d.decided_at else None,
                "decided_by": d.decided_by,
                "notes": d.notes,
            }

            # Include override reasons if it's an override decision
            if d.decision_type == "override":
                reasons = (
                    db.query(OverrideReason)
                    .filter(OverrideReason.decision_id == d.id)
                    .all()
                )
                decision_data["override_reasons"] = [
                    {
                        "field_changed": r.field_changed,
                        "old_value": r.old_value,
                        "new_value": r.new_value,
                        "reason": r.reason,
                    }
                    for r in reasons
                ]

            decision_list.append(decision_data)

        # Build runs and flattened stops
        runs = []
        stops = []
        for run in sorted(plan.runs, key=lambda current: (current.dispatch_day, current.id or 0)):
            lorry = db.query(Lorry).filter(Lorry.id == run.lorry_id).first()
            run_stops = []
            for stop in sorted(run.stops, key=lambda current: (current.stop_sequence, current.id or 0)):
                dc = db.query(DC).filter(DC.id == stop.dc_id).first()

                items = []
                for item in stop.items:
                    sku = db.query(SKU).filter(SKU.id == item.sku_id).first()
                    items.append({
                        "sku_id": item.sku_id,
                        "sku_code": sku.code if sku else "UNKNOWN",
                        "sku_name": sku.name if sku else "Unknown",
                        "quantity": item.quantity,
                    })

                stop_payload = {
                    "id": stop.id,
                    "stop_sequence": stop.stop_sequence,
                    "dc_id": stop.dc_id,
                    "dc_code": dc.code if dc else "UNKNOWN",
                    "dc_name": dc.name if dc else "Unknown",
                    "items": items,
                }
                run_stops.append(stop_payload)
                stops.append({
                    **stop_payload,
                    "dispatch_day": run.dispatch_day,
                    "lorry_id": run.lorry_id,
                    "registration": lorry.registration if lorry else "UNKNOWN",
                    "lorry_type": lorry.lorry_type if lorry else "unknown",
                })

            runs.append({
                "id": run.id,
                "lorry_id": run.lorry_id,
                "registration": lorry.registration if lorry else "UNKNOWN",
                "lorry_type": lorry.lorry_type if lorry else "unknown",
                "dispatch_day": run.dispatch_day,
                "stops": run_stops,
            })

        result.append({
            "id": plan.id,
            "engine_run_id": plan.engine_run_id,
            "version_number": plan.version_number,
            "score": plan.score,
            "approved_at": plan.approved_at.isoformat() if plan.approved_at else None,
            "approved_by": plan.approved_by,
            "runs": runs,
            "stops": stops,
            "decisions": decision_list,
        })

    return {"approved_plans": result, "count": len(result)}


@router.get("/audit-trail")
def get_audit_trail(
    entity_type: Optional[str] = None,
    action: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """Get audit log entries, optionally filtered by entity type or action."""
    query = db.query(AuditLog).order_by(AuditLog.timestamp.desc())

    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)
    if action:
        query = query.filter(AuditLog.action == action)

    logs = query.limit(limit).all()

    return {
        "audit_trail": [
            {
                "id": log.id,
                "entity_type": log.entity_type,
                "entity_id": log.entity_id,
                "action": log.action,
                "actor": log.actor,
                "timestamp": log.timestamp.isoformat() if log.timestamp else None,
                "details": log.details,
            }
            for log in logs
        ],
        "count": len(logs),
    }
