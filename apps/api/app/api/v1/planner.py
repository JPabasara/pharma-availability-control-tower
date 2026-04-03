"""Planner flow endpoints for current/live views and legacy run-id debug views."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from apps.api.app.dependencies.database import get_db
from apps.api.app.orchestration import service as orchestration_service
from apps.api.app.planner_flow import service as planner_service
from storage.models import (
    DC,
    EngineRun,
    Lorry,
    M1Result,
    M2Request,
    M3PlanRun,
    M3PlanStop,
    M3PlanVersion,
    SKU,
)

router = APIRouter(prefix="/api/v1/planner", tags=["planner"])


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


def _serialize_m1_results(run: EngineRun | None, results: list[M1Result]) -> dict:
    line_results = []
    sku_agg: dict[int, dict] = {}

    for result in results:
        sku = result.sku
        if not sku:
            sku = None

        line_results.append(
            {
                "id": result.id,
                "manifest_line_id": result.manifest_line_id,
                "sku_id": result.sku_id,
                "sku_code": sku.code if sku else "UNKNOWN",
                "sku_name": sku.name if sku else "Unknown",
                "priority_score": result.priority_score,
                "priority_band": result.priority_band,
                "reefer_required": result.reefer_required,
            }
        )

        summary = sku_agg.setdefault(
            result.sku_id,
            {
                "sku_id": result.sku_id,
                "sku_code": sku.code if sku else "UNKNOWN",
                "sku_name": sku.name if sku else "Unknown",
                "reefer_required": result.reefer_required,
                "scores": [],
                "bands": [],
            },
        )
        summary["scores"].append(result.priority_score)
        summary["bands"].append(result.priority_band)

    sku_summary = []
    band_priority = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    for data in sku_agg.values():
        highest_band = min(data["bands"], key=lambda band: band_priority.get(band, 99))
        sku_summary.append(
            {
                "sku_id": data["sku_id"],
                "sku_code": data["sku_code"],
                "sku_name": data["sku_name"],
                "reefer_required": data["reefer_required"],
                "avg_score": round(sum(data["scores"]) / len(data["scores"]), 2),
                "max_score": max(data["scores"]),
                "line_count": len(data["scores"]),
                "highest_band": highest_band,
            }
        )

    return {
        "available": run is not None,
        "run_id": run.id if run else None,
        "status": run.status if run else "not_started",
        "generated_at": orchestration_service.get_generated_at_iso(run),
        "planning_start_date": run.planning_start_date.isoformat() if run and run.planning_start_date else None,
        "line_results": line_results,
        "sku_summary": sorted(sku_summary, key=lambda item: item["max_score"], reverse=True),
        "total_lines": len(line_results),
    }


def _serialize_m2_requests(run: EngineRun | None, requests: list[M2Request]) -> dict:
    result_list = []
    for request in requests:
        sku = request.sku
        dc = request.dc
        result_list.append(
            {
                "id": request.id,
                "dc_id": request.dc_id,
                "dc_code": dc.code if dc else "UNKNOWN",
                "dc_name": dc.name if dc else "Unknown",
                "sku_id": request.sku_id,
                "sku_code": sku.code if sku else "UNKNOWN",
                "sku_name": sku.name if sku else "Unknown",
                "requested_quantity": request.requested_quantity,
                "urgency": request.urgency,
                "required_by": request.required_by.isoformat() if request.required_by else None,
            }
        )

    return {
        "available": run is not None,
        "run_id": run.id if run else None,
        "status": run.status if run else "not_started",
        "generated_at": orchestration_service.get_generated_at_iso(run),
        "planning_start_date": run.planning_start_date.isoformat() if run and run.planning_start_date else None,
        "requests": result_list,
        "total_requests": len(result_list),
    }


def _load_m3_plan_detail(session: Session, plan_version_id: int) -> M3PlanVersion | None:
    return (
        session.query(M3PlanVersion)
        .options(
            joinedload(M3PlanVersion.runs)
            .joinedload(M3PlanRun.stops)
            .joinedload(M3PlanStop.items),
            joinedload(M3PlanVersion.engine_run),
        )
        .filter(M3PlanVersion.id == plan_version_id)
        .first()
    )


def _serialize_m3_plan_summary(plan: M3PlanVersion) -> dict:
    return {
        "id": plan.id,
        "version_number": plan.version_number,
        "plan_status": plan.plan_status,
        "score": plan.score,
        "is_best": plan.is_best,
        "approved_at": plan.approved_at.isoformat() if plan.approved_at else None,
        "approved_by": plan.approved_by,
        "run_count": len(plan.runs),
        "stop_count": len(plan.stops),
    }


def _serialize_m3_plan_detail(plan: M3PlanVersion) -> dict:
    runs = []
    stops = []
    total_items = 0

    for run in sorted(plan.runs, key=lambda current: (current.dispatch_day, current.id or 0)):
        lorry = run.lorry
        run_stops = []

        for stop in sorted(run.stops, key=lambda current: (current.stop_sequence, current.id or 0)):
            dc = stop.dc
            items = []
            for item in stop.items:
                sku = item.sku
                items.append(
                    {
                        "id": item.id,
                        "sku_id": item.sku_id,
                        "sku_code": sku.code if sku else "UNKNOWN",
                        "sku_name": sku.name if sku else "Unknown",
                        "quantity": item.quantity,
                    }
                )
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
            stops.append(
                {
                    **stop_payload,
                    "lorry_id": run.lorry_id,
                    "registration": lorry.registration if lorry else "UNKNOWN",
                    "lorry_type": lorry.lorry_type if lorry else "unknown",
                    "capacity_units": lorry.capacity_units if lorry else 0,
                    "dispatch_day": run.dispatch_day,
                }
            )

        runs.append(
            {
                "id": run.id,
                "lorry_id": run.lorry_id,
                "registration": lorry.registration if lorry else "UNKNOWN",
                "lorry_type": lorry.lorry_type if lorry else "unknown",
                "capacity_units": lorry.capacity_units if lorry else 0,
                "dispatch_day": run.dispatch_day,
                "stops": run_stops,
                "total_stops": len(run_stops),
            }
        )

    engine_run = plan.engine_run
    return {
        "id": plan.id,
        "run_id": engine_run.id if engine_run else None,
        "version_number": plan.version_number,
        "plan_status": plan.plan_status,
        "score": plan.score,
        "is_best": plan.is_best,
        "approved_at": plan.approved_at.isoformat() if plan.approved_at else None,
        "approved_by": plan.approved_by,
        "generated_at": orchestration_service.get_generated_at_iso(engine_run),
        "planning_start_date": (
            engine_run.planning_start_date.isoformat()
            if engine_run and engine_run.planning_start_date
            else None
        ),
        "runs": runs,
        "stops": stops,
        "total_runs": len(runs),
        "total_stops": len(stops),
        "total_items": total_items,
    }


@router.get("/m1-results/current")
def get_current_m1_results(db: Session = Depends(get_db)):
    """Return the current singleton M1 result set."""
    run = orchestration_service.get_latest_engine_run(db, "m1")
    if not run:
        return _serialize_m1_results(None, [])

    results = (
        db.query(M1Result)
        .options(joinedload(M1Result.sku))
        .filter(M1Result.engine_run_id == run.id)
        .order_by(M1Result.priority_score.desc(), M1Result.id.asc())
        .all()
    )
    return _serialize_m1_results(run, results)


@router.get("/m2-requests/current")
def get_current_m2_requests(db: Session = Depends(get_db)):
    """Return the current singleton M2 request set."""
    run = orchestration_service.get_latest_engine_run(db, "m2")
    if not run:
        return _serialize_m2_requests(None, [])

    requests = (
        db.query(M2Request)
        .options(joinedload(M2Request.sku), joinedload(M2Request.dc))
        .filter(M2Request.engine_run_id == run.id)
        .order_by(M2Request.id.asc())
        .all()
    )
    return _serialize_m2_requests(run, requests)


@router.get("/m3-plans/current")
def get_current_m3_plans(db: Session = Depends(get_db)):
    """Return the current live M3 draft candidate set plus lock metadata."""
    plans, run = orchestration_service.get_current_m3_draft_plans(db)
    latest_run = run or orchestration_service.get_latest_engine_run(db, "m3")
    lock_state = orchestration_service.get_m3_lock_state(db)

    return {
        "available": bool(plans),
        "run_id": latest_run.id if latest_run else None,
        "status": latest_run.status if latest_run else "not_started",
        "generated_at": orchestration_service.get_generated_at_iso(latest_run),
        "planning_start_date": (
            run.planning_start_date.isoformat()
            if run and run.planning_start_date
            else lock_state["planning_start_date"]
        ),
        "locked": lock_state["locked"],
        "lock_reason": lock_state["lock_reason"],
        "plans": [_serialize_m3_plan_summary(plan) for plan in plans],
        "total_plans": len(plans),
    }


@router.get("/m3-plans/current/{plan_version_id}")
def get_current_m3_plan_detail(plan_version_id: int, db: Session = Depends(get_db)):
    """Return detail for a plan that belongs to the current live draft set."""
    current_plans, _ = orchestration_service.get_current_m3_draft_plans(db)
    current_plan_ids = {plan.id for plan in current_plans}
    if plan_version_id not in current_plan_ids:
        raise HTTPException(status_code=404, detail="Current candidate plan not found.")

    plan = _load_m3_plan_detail(db, plan_version_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Current candidate plan not found.")
    return _serialize_m3_plan_detail(plan)


@router.get("/m1-results/{run_id}")
def get_m1_results(run_id: int, db: Session = Depends(get_db)):
    """Legacy/debug route for a specific M1 engine run."""
    run = (
        db.query(EngineRun)
        .filter(EngineRun.id == run_id, EngineRun.engine_type == "m1")
        .first()
    )
    if not run:
        raise HTTPException(status_code=404, detail=f"M1 engine run {run_id} not found.")

    results = (
        db.query(M1Result)
        .options(joinedload(M1Result.sku))
        .filter(M1Result.engine_run_id == run_id)
        .order_by(M1Result.priority_score.desc(), M1Result.id.asc())
        .all()
    )
    return _serialize_m1_results(run, results)


@router.get("/m2-requests/{run_id}")
def get_m2_requests(run_id: int, db: Session = Depends(get_db)):
    """Legacy/debug route for a specific M2 engine run."""
    run = (
        db.query(EngineRun)
        .filter(EngineRun.id == run_id, EngineRun.engine_type == "m2")
        .first()
    )
    if not run:
        raise HTTPException(status_code=404, detail=f"M2 engine run {run_id} not found.")

    requests = (
        db.query(M2Request)
        .options(joinedload(M2Request.sku), joinedload(M2Request.dc))
        .filter(M2Request.engine_run_id == run_id)
        .order_by(M2Request.id.asc())
        .all()
    )
    return _serialize_m2_requests(run, requests)


@router.get("/m3-plans/{run_id}")
def get_m3_plans(run_id: int, db: Session = Depends(get_db)):
    """Legacy/debug route for all M3 candidate plans in a specific run."""
    run = (
        db.query(EngineRun)
        .filter(EngineRun.id == run_id, EngineRun.engine_type == "m3")
        .first()
    )
    if not run:
        raise HTTPException(status_code=404, detail=f"M3 engine run {run_id} not found.")

    plans = (
        db.query(M3PlanVersion)
        .options(joinedload(M3PlanVersion.runs).joinedload(M3PlanRun.stops))
        .filter(M3PlanVersion.engine_run_id == run_id)
        .order_by(M3PlanVersion.version_number.asc(), M3PlanVersion.id.asc())
        .all()
    )

    return {
        "available": bool(plans),
        "run_id": run.id,
        "status": run.status,
        "generated_at": orchestration_service.get_generated_at_iso(run),
        "planning_start_date": run.planning_start_date.isoformat() if run.planning_start_date else None,
        "plans": [_serialize_m3_plan_summary(plan) for plan in plans],
        "total_plans": len(plans),
    }


@router.get("/m3-plans/{run_id}/{version_id}")
def get_m3_plan_detail(run_id: int, version_id: int, db: Session = Depends(get_db)):
    """Legacy/debug route for a specific M3 plan version."""
    plan = _load_m3_plan_detail(db, version_id)
    if not plan or plan.engine_run_id != run_id:
        raise HTTPException(
            status_code=404,
            detail=f"Plan version {version_id} for run {run_id} not found.",
        )
    return _serialize_m3_plan_detail(plan)


@router.post("/approve/{plan_version_id}")
def approve_plan(plan_version_id: int, db: Session = Depends(get_db)):
    """Approve a draft plan version."""
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
    """Reject a draft plan version and regenerate a fresh singleton set."""
    notes = body.notes if body else ""
    rejected_by = body.rejected_by if body else "planner"
    result = planner_service.reject_plan(
        db,
        plan_version_id,
        notes=notes,
        rejected_by=rejected_by,
    )
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@router.post("/override/{plan_version_id}")
def override_plan(
    plan_version_id: int,
    body: OverrideRequest,
    db: Session = Depends(get_db),
):
    """Override a live draft plan in place, validated by the math-bound check."""
    changes = [change.model_dump(exclude_none=True) for change in body.changes]
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
