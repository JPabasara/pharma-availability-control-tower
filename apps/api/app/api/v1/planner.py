"""Planner flow endpoints — view engine results, approve, reject, override plans.

Routes:
    GET  /api/v1/planner/m1-results/{run_id}                — M1 line scores + SKU summary
    GET  /api/v1/planner/m2-requests/{run_id}               — M2 DC requests
    GET  /api/v1/planner/m3-plans/{run_id}                  — M3 candidate plans
    GET  /api/v1/planner/m3-plans/{run_id}/{version_id}     — specific plan detail
    POST /api/v1/planner/approve/{plan_version_id}          — approve plan
    POST /api/v1/planner/reject/{plan_version_id}           — reject plan
    POST /api/v1/planner/override/{plan_version_id}         — override + validate
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from apps.api.app.dependencies.database import get_db
from apps.api.app.planner_flow import service as planner_service
from storage.models import (
    EngineRun,
    M1Result,
    M2Request,
    M3PlanRun,
    M3PlanVersion,
    M3PlanStop,
    M3PlanItem,
    SKU,
    DC,
    Lorry,
)

router = APIRouter(prefix="/api/v1/planner", tags=["planner"])


# ── Request schemas ─────────────────────────────────────────────────────

class RejectRequest(BaseModel):
    notes: str = ""
    rejected_by: str = "planner"


class OverrideItemSchema(BaseModel):
    sku_id: int
    quantity: int


class OverrideStopSchema(BaseModel):
    dc_id: int
    stop_sequence: int | None = None
    items: list[OverrideItemSchema] = []


class OverrideRunSchema(BaseModel):
    lorry_id: int
    dispatch_day: int
    stops: list[OverrideStopSchema]


class OverrideRequest(BaseModel):
    changes: list[OverrideRunSchema]
    notes: str = ""
    override_by: str = "planner"


# ── M1 results ──────────────────────────────────────────────────────────

@router.get("/m1-results/{run_id}")
def get_m1_results(run_id: int, db: Session = Depends(get_db)):
    """Get M1 priority scores for a specific engine run.

    Returns line-level scores AND an aggregated SKU summary.
    """
    run = db.query(EngineRun).filter(
        EngineRun.id == run_id, EngineRun.engine_type == "m1"
    ).first()
    if not run:
        raise HTTPException(status_code=404, detail=f"M1 engine run {run_id} not found.")

    results = db.query(M1Result).filter(M1Result.engine_run_id == run_id).all()

    # Build line-level results
    line_results = []
    for r in results:
        sku = db.query(SKU).filter(SKU.id == r.sku_id).first()
        line_results.append({
            "id": r.id,
            "manifest_line_id": r.manifest_line_id,
            "sku_id": r.sku_id,
            "sku_code": sku.code if sku else "UNKNOWN",
            "sku_name": sku.name if sku else "Unknown",
            "priority_score": r.priority_score,
            "priority_band": r.priority_band,
            "reefer_required": r.reefer_required,
        })

    # Build aggregated SKU summary
    sku_agg: dict[int, dict] = {}
    for r in results:
        if r.sku_id not in sku_agg:
            sku = db.query(SKU).filter(SKU.id == r.sku_id).first()
            sku_agg[r.sku_id] = {
                "sku_id": r.sku_id,
                "sku_code": sku.code if sku else "UNKNOWN",
                "sku_name": sku.name if sku else "Unknown",
                "reefer_required": r.reefer_required,
                "scores": [],
                "bands": [],
            }
        sku_agg[r.sku_id]["scores"].append(r.priority_score)
        sku_agg[r.sku_id]["bands"].append(r.priority_band)

    sku_summary = []
    for data in sku_agg.values():
        scores = data["scores"]
        bands = data["bands"]
        # Determine highest band
        band_priority = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        highest_band = min(bands, key=lambda b: band_priority.get(b, 99))
        sku_summary.append({
            "sku_id": data["sku_id"],
            "sku_code": data["sku_code"],
            "sku_name": data["sku_name"],
            "reefer_required": data["reefer_required"],
            "avg_score": round(sum(scores) / len(scores), 2),
            "max_score": max(scores),
            "line_count": len(scores),
            "highest_band": highest_band,
        })

    return {
        "run_id": run_id,
        "status": run.status,
        "line_results": line_results,
        "sku_summary": sorted(sku_summary, key=lambda x: x["max_score"], reverse=True),
        "total_lines": len(line_results),
    }


# ── M2 requests ────────────────────────────────────────────────────────

@router.get("/m2-requests/{run_id}")
def get_m2_requests(run_id: int, db: Session = Depends(get_db)):
    """Get M2 DC replenishment requests for a specific engine run."""
    run = db.query(EngineRun).filter(
        EngineRun.id == run_id, EngineRun.engine_type == "m2"
    ).first()
    if not run:
        raise HTTPException(status_code=404, detail=f"M2 engine run {run_id} not found.")

    requests = db.query(M2Request).filter(M2Request.engine_run_id == run_id).all()

    result_list = []
    for req in requests:
        sku = db.query(SKU).filter(SKU.id == req.sku_id).first()
        dc = db.query(DC).filter(DC.id == req.dc_id).first()
        result_list.append({
            "id": req.id,
            "dc_id": req.dc_id,
            "dc_code": dc.code if dc else "UNKNOWN",
            "dc_name": dc.name if dc else "Unknown",
            "sku_id": req.sku_id,
            "sku_code": sku.code if sku else "UNKNOWN",
            "sku_name": sku.name if sku else "Unknown",
            "requested_quantity": req.requested_quantity,
            "urgency": req.urgency,
            "required_by": req.required_by.isoformat() if req.required_by else None,
        })

    return {
        "run_id": run_id,
        "status": run.status,
        "requests": result_list,
        "total_requests": len(result_list),
    }


# ── M3 plans ───────────────────────────────────────────────────────────

@router.get("/m3-plans/{run_id}")
def get_m3_plans(run_id: int, db: Session = Depends(get_db)):
    """Get all M3 candidate plans for a specific engine run."""
    run = db.query(EngineRun).filter(
        EngineRun.id == run_id, EngineRun.engine_type == "m3"
    ).first()
    if not run:
        raise HTTPException(status_code=404, detail=f"M3 engine run {run_id} not found.")

    plans = (
        db.query(M3PlanVersion)
        .filter(M3PlanVersion.engine_run_id == run_id)
        .order_by(M3PlanVersion.version_number)
        .all()
    )

    plan_list = []
    for p in plans:
        plan_list.append({
            "id": p.id,
            "version_number": p.version_number,
            "plan_status": p.plan_status,
            "score": p.score,
            "is_best": p.is_best,
            "approved_at": p.approved_at.isoformat() if p.approved_at else None,
            "approved_by": p.approved_by,
            "run_count": len(p.runs),
            "stop_count": len(p.stops),
        })

    return {
        "run_id": run_id,
        "status": run.status,
        "plans": plan_list,
        "total_plans": len(plan_list),
    }


@router.get("/m3-plans/{run_id}/{version_id}")
def get_m3_plan_detail(run_id: int, version_id: int, db: Session = Depends(get_db)):
    """Get full detail of a specific M3 plan version including stops and items."""
    plan = (
        db.query(M3PlanVersion)
        .options(
            joinedload(M3PlanVersion.runs)
            .joinedload(M3PlanRun.stops)
            .joinedload(M3PlanStop.items)
        )
        .filter(M3PlanVersion.id == version_id, M3PlanVersion.engine_run_id == run_id)
        .first()
    )
    if not plan:
        raise HTTPException(
            status_code=404,
            detail=f"Plan version {version_id} for run {run_id} not found.",
        )

    runs = []
    stops = []
    total_items = 0
    for run in sorted(plan.runs, key=lambda current: (current.dispatch_day, current.id or 0)):
        lorry = db.query(Lorry).filter(Lorry.id == run.lorry_id).first()
        run_stops = []

        for stop in sorted(run.stops, key=lambda current: (current.stop_sequence, current.id or 0)):
            dc = db.query(DC).filter(DC.id == stop.dc_id).first()
            items = []
            for item in stop.items:
                sku = db.query(SKU).filter(SKU.id == item.sku_id).first()
                items.append({
                    "id": item.id,
                    "sku_id": item.sku_id,
                    "sku_code": sku.code if sku else "UNKNOWN",
                    "sku_name": sku.name if sku else "Unknown",
                    "quantity": item.quantity,
                })
                total_items += 1

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
                "lorry_id": run.lorry_id,
                "registration": lorry.registration if lorry else "UNKNOWN",
                "lorry_type": lorry.lorry_type if lorry else "unknown",
                "capacity_units": lorry.capacity_units if lorry else 0,
                "dispatch_day": run.dispatch_day,
            })

        runs.append({
            "id": run.id,
            "lorry_id": run.lorry_id,
            "registration": lorry.registration if lorry else "UNKNOWN",
            "lorry_type": lorry.lorry_type if lorry else "unknown",
            "capacity_units": lorry.capacity_units if lorry else 0,
            "dispatch_day": run.dispatch_day,
            "stops": run_stops,
            "total_stops": len(run_stops),
        })

    return {
        "id": plan.id,
        "run_id": run_id,
        "version_number": plan.version_number,
        "plan_status": plan.plan_status,
        "score": plan.score,
        "is_best": plan.is_best,
        "approved_at": plan.approved_at.isoformat() if plan.approved_at else None,
        "approved_by": plan.approved_by,
        "runs": runs,
        "stops": stops,
        "total_runs": len(runs),
        "total_stops": len(stops),
        "total_items": total_items,
    }


# ── Planner actions ────────────────────────────────────────────────────

@router.post("/approve/{plan_version_id}")
def approve_plan(plan_version_id: int, db: Session = Depends(get_db)):
    """Approve a draft plan version.

    Freezes plan as immutable, creates demo_reservations and demo_transfers.
    """
    result = planner_service.approve_plan(db, plan_version_id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@router.post("/reject/{plan_version_id}")
def reject_plan(
    plan_version_id: int,
    body: RejectRequest | None = None,
    db: Session = Depends(get_db),
):
    """Reject a draft plan version."""
    notes = body.notes if body else ""
    rejected_by = body.rejected_by if body else "planner"
    result = planner_service.reject_plan(db, plan_version_id, notes=notes, rejected_by=rejected_by)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@router.post("/override/{plan_version_id}")
def override_plan(
    plan_version_id: int,
    body: OverrideRequest,
    db: Session = Depends(get_db),
):
    """Override a plan with changes, validated by math-bound check.

    Creates a new draft version if validation passes.
    """
    changes = [c.model_dump(exclude_none=True) for c in body.changes]
    result = planner_service.override_plan(
        db,
        plan_version_id,
        changes=changes,
        override_by=body.override_by,
        notes=body.notes,
    )
    if not result["success"]:
        status_code = 422 if "validation" in result else 400
        raise HTTPException(status_code=status_code, detail=result)
    return result
