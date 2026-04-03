"""Dashboard summary endpoint for live planner visibility."""

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from apps.api.app.dependencies.business_time import get_planning_dates
from apps.api.app.dependencies.database import get_db
from apps.api.app.orchestration import service as orchestration_service
from integrations.inbound.dc_stock_reader import reader as dc_reader
from integrations.inbound.lorry_state_reader import reader as lorry_reader
from integrations.inbound.warehouse_stock_reader import reader as wh_reader
from storage.models import ManifestSnapshot, M3PlanVersion, SKU

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


def _snapshot(run) -> dict:
    return {
        "available": run is not None,
        "generated_at": orchestration_service.get_generated_at_iso(run),
        "planning_start_date": run.planning_start_date.isoformat() if run and run.planning_start_date else None,
    }


@router.get("/summary")
def get_dashboard_summary(db: Session = Depends(get_db)):
    """Return planner dashboard summary data without exposing draft run numbering."""
    approved_count = (
        db.query(func.count(M3PlanVersion.id))
        .filter(M3PlanVersion.plan_status == "approved")
        .scalar()
        or 0
    )

    active_manifests = (
        db.query(func.count(ManifestSnapshot.id))
        .filter(ManifestSnapshot.status == "active")
        .scalar()
        or 0
    )

    planning_dates = get_planning_dates()
    fleet_status = {
        "business_date": planning_dates[0].isoformat(),
        "total": 0,
        "available": 0,
        "unavailable": 0,
        "assigned": 0,
    }
    reefer_available = 0
    lorry_contract = lorry_reader.get_latest_contract(db)
    if lorry_contract:
        fleet_status["business_date"] = lorry_contract["planning_dates"][0]
        for lorry in lorry_contract["lorries"]:
            fleet_status["total"] += 1
            status = lorry["day1_status"]
            if status == "available":
                fleet_status["available"] += 1
                if lorry["lorry_type"] == "reefer":
                    reefer_available += 1
            elif status == "assigned":
                fleet_status["assigned"] += 1
            else:
                fleet_status["unavailable"] += 1

    alerts = []
    try:
        dc_contracts = dc_reader.get_all_latest_contracts(db)
        for dc in dc_contracts:
            low_stock_skus = [item for item in dc.get("items", []) if item.get("effective", 0) < 200]
            if low_stock_skus:
                alerts.append(
                    {
                        "type": "low_dc_stock",
                        "severity": "critical" if any(item["effective"] < 50 for item in low_stock_skus) else "warning",
                        "message": (
                            f"{dc.get('dc_name', 'Unknown DC')} ({dc.get('dc_code', '?')}) has "
                            f"{len(low_stock_skus)} SKU(s) with low effective stock."
                        ),
                        "dc_id": dc.get("dc_id"),
                        "details": [
                            {"sku_code": item["sku_code"], "effective": item["effective"]}
                            for item in low_stock_skus[:5]
                        ],
                    }
                )
    except Exception:
        pass

    try:
        wh_contract = wh_reader.get_latest_contract(db)
        if wh_contract:
            critical_wh = [item for item in wh_contract.get("items", []) if item.get("effective", 0) < 500]
            if critical_wh:
                alerts.append(
                    {
                        "type": "low_wh_stock",
                        "severity": "warning",
                        "message": f"Warehouse has {len(critical_wh)} SKU(s) with low effective stock.",
                        "details": [
                            {"sku_code": item["sku_code"], "effective": item["effective"]}
                            for item in critical_wh[:5]
                        ],
                    }
                )
    except Exception:
        pass

    reefer_skus = db.query(func.count(SKU.id)).filter(SKU.reefer_required == True).scalar() or 0
    if reefer_skus > 0 and reefer_available < reefer_skus:
        alerts.append(
            {
                "type": "reefer_pressure",
                "severity": "warning",
                "message": (
                    f"{reefer_skus} reefer SKUs need dispatch but only "
                    f"{reefer_available} reefer lorries are available tomorrow."
                ),
            }
        )

    return {
        "approved_plans": approved_count,
        "active_manifests": active_manifests,
        "live_snapshots": {
            "m1": _snapshot(orchestration_service.get_latest_engine_run(db, "m1")),
            "m2": _snapshot(orchestration_service.get_latest_engine_run(db, "m2")),
            "m3": _snapshot(orchestration_service.get_latest_engine_run(db, "m3")),
        },
        "m3_lock": orchestration_service.get_m3_lock_state(db),
        "fleet_status": fleet_status,
        "alerts": alerts,
        "alert_count": len(alerts),
    }
