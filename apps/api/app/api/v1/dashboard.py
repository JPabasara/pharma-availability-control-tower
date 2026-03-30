"""Dashboard summary endpoint — aggregated overview for the planner console.

Routes:
    GET /api/v1/dashboard/summary   — aggregated dashboard data
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from apps.api.app.dependencies.database import get_db
from storage.models import (
    EngineRun,
    M3PlanVersion,
    ManifestSnapshot,
    SKU,
    Lorry,
    LorryStateSnapshot,
    LorryStateItem,
)
from integrations.inbound.warehouse_stock_reader import reader as wh_reader
from integrations.inbound.dc_stock_reader import reader as dc_reader

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


@router.get("/summary")
def get_dashboard_summary(db: Session = Depends(get_db)):
    """Get aggregated dashboard data for the planner console.

    Returns:
        - pending_approvals: count of draft plans awaiting action
        - critical_alerts: low stock DCs, reefer pressure warnings
        - latest_engine_run: info about the most recent engine execution
        - active_manifests: count of active vessel manifests
        - fleet_status: lorry availability overview
    """

    # ── Pending approvals ───────────────────────────────────────────────
    pending_count = (
        db.query(func.count(M3PlanVersion.id))
        .filter(M3PlanVersion.plan_status == "draft")
        .scalar() or 0
    )

    approved_count = (
        db.query(func.count(M3PlanVersion.id))
        .filter(M3PlanVersion.plan_status == "approved")
        .scalar() or 0
    )

    # ── Active manifests ────────────────────────────────────────────────
    active_manifests = (
        db.query(func.count(ManifestSnapshot.id))
        .filter(ManifestSnapshot.status == "active")
        .scalar() or 0
    )

    # ── Latest engine run ───────────────────────────────────────────────
    latest_run = (
        db.query(EngineRun)
        .order_by(desc(EngineRun.started_at))
        .first()
    )
    latest_run_info = None
    if latest_run:
        latest_run_info = {
            "id": latest_run.id,
            "engine_type": latest_run.engine_type,
            "started_at": latest_run.started_at.isoformat() if latest_run.started_at else None,
            "completed_at": latest_run.completed_at.isoformat() if latest_run.completed_at else None,
            "status": latest_run.status,
        }

    # ── Fleet status ────────────────────────────────────────────────────
    latest_lorry_snap = (
        db.query(LorryStateSnapshot)
        .order_by(desc(LorryStateSnapshot.snapshot_time))
        .first()
    )
    fleet_status = {"total": 0, "available": 0, "unavailable": 0, "reefer_available": 0, "normal_available": 0}
    if latest_lorry_snap:
        items = db.query(LorryStateItem).filter(
            LorryStateItem.snapshot_id == latest_lorry_snap.id
        ).all()
        for item in items:
            lorry = db.query(Lorry).filter(Lorry.id == item.lorry_id).first()
            fleet_status["total"] += 1
            if item.status == "available":
                fleet_status["available"] += 1
                if lorry and lorry.lorry_type == "reefer":
                    fleet_status["reefer_available"] += 1
                elif lorry:
                    fleet_status["normal_available"] += 1
            else:
                fleet_status["unavailable"] += 1

    # ── Critical alerts ─────────────────────────────────────────────────
    alerts = []

    # Check DC stock for low-stock alerts
    try:
        dc_contracts = dc_reader.get_all_latest_contracts(db)
        for dc in dc_contracts:
            low_stock_skus = [
                item for item in dc.get("items", [])
                if item.get("effective", 0) < 200
            ]
            if low_stock_skus:
                alerts.append({
                    "type": "low_dc_stock",
                    "severity": "critical" if any(i["effective"] < 50 for i in low_stock_skus) else "warning",
                    "message": f"{dc.get('dc_name', 'Unknown DC')} ({dc.get('dc_code', '?')}) has "
                               f"{len(low_stock_skus)} SKU(s) with low effective stock.",
                    "dc_id": dc.get("dc_id"),
                    "details": [
                        {"sku_code": i["sku_code"], "effective": i["effective"]}
                        for i in low_stock_skus[:5]
                    ],
                })
    except Exception:
        pass  # Don't fail dashboard if stock read fails

    # Check WH stock for low-stock alerts
    try:
        wh_contract = wh_reader.get_latest_contract(db)
        if wh_contract:
            critical_wh = [
                item for item in wh_contract.get("items", [])
                if item.get("effective", 0) < 500
            ]
            if critical_wh:
                alerts.append({
                    "type": "low_wh_stock",
                    "severity": "warning",
                    "message": f"Warehouse has {len(critical_wh)} SKU(s) with low effective stock.",
                    "details": [
                        {"sku_code": i["sku_code"], "effective": i["effective"]}
                        for i in critical_wh[:5]
                    ],
                })
    except Exception:
        pass

    # Reefer pressure check
    reefer_skus = db.query(func.count(SKU.id)).filter(SKU.reefer_required == True).scalar() or 0
    if reefer_skus > 0 and fleet_status["reefer_available"] < reefer_skus:
        alerts.append({
            "type": "reefer_pressure",
            "severity": "warning",
            "message": f"{reefer_skus} reefer SKUs need dispatch but only "
                       f"{fleet_status['reefer_available']} reefer lorries are available.",
        })

    return {
        "pending_approvals": pending_count,
        "approved_plans": approved_count,
        "active_manifests": active_manifests,
        "latest_engine_run": latest_run_info,
        "fleet_status": fleet_status,
        "alerts": alerts,
        "alert_count": len(alerts),
    }
