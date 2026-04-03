"""Orchestration endpoints — trigger plan generation and view engine runs.

Routes:
    POST /api/v1/orchestration/generate-plan   — trigger full M2→M1→M3 pipeline
    GET  /api/v1/orchestration/runs            — list engine runs
    GET  /api/v1/orchestration/runs/{run_id}   — specific run details
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from apps.api.app.dependencies.database import get_db
from apps.api.app.orchestration import service as orchestration_service
from storage.models import EngineRun, M1Result, M2Request, M3PlanVersion

router = APIRouter(prefix="/api/v1/orchestration", tags=["orchestration"])


@router.post("/refresh-m2")
def refresh_m2(db: Session = Depends(get_db)):
    """Trigger the M2 engine isolated run."""
    try:
        result = orchestration_service.refresh_m2(db)
        return {
            "success": True,
            "message": "M2 refreshed successfully.",
            **result,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"M2 refresh failed: {str(e)}")


@router.post("/refresh-m1")
def refresh_m1(db: Session = Depends(get_db)):
    """Trigger the M1 engine isolated run."""
    try:
        result = orchestration_service.refresh_m1(db)
        return {
            "success": True,
            "message": "M1 refreshed successfully.",
            **result,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"M1 refresh failed: {str(e)}")


@router.post("/generate-plan")
def generate_plan(db: Session = Depends(get_db)):
    """Trigger the M3 dispatch generation (locking and singleton check applied).

    This is the main action triggered by the planner clicking 'Generate Plan'.
    """
    try:
        result = orchestration_service.generate_plan(db)
        return {
            "success": True,
            "message": "Plan generated successfully.",
            **result,
        }
    except ValueError as e:
        # Lock validation exception
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Plan generation failed: {str(e)}")


@router.get("/runs")
def list_engine_runs(
    engine_type: str | None = None,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    """List engine runs, optionally filtered by type (m1, m2, m3)."""
    query = db.query(EngineRun).order_by(EngineRun.started_at.desc())

    if engine_type:
        query = query.filter(EngineRun.engine_type == engine_type)

    runs = query.limit(limit).all()

    return {
        "runs": [
            {
                "id": r.id,
                "engine_type": r.engine_type,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                "status": r.status,
                "input_snapshot_ids": r.input_snapshot_ids,
            }
            for r in runs
        ],
        "count": len(runs),
    }


@router.get("/runs/{run_id}")
def get_engine_run(run_id: int, db: Session = Depends(get_db)):
    """Get details of a specific engine run including its results."""
    run = db.query(EngineRun).filter(EngineRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail=f"Engine run {run_id} not found.")

    result = {
        "id": run.id,
        "engine_type": run.engine_type,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "status": run.status,
        "input_snapshot_ids": run.input_snapshot_ids,
    }

    # Attach type-specific results
    if run.engine_type == "m1":
        m1_results = db.query(M1Result).filter(M1Result.engine_run_id == run.id).all()
        result["m1_results"] = [
            {
                "id": r.id,
                "manifest_line_id": r.manifest_line_id,
                "sku_id": r.sku_id,
                "priority_score": r.priority_score,
                "priority_band": r.priority_band,
                "reefer_required": r.reefer_required,
            }
            for r in m1_results
        ]
    elif run.engine_type == "m2":
        m2_requests = db.query(M2Request).filter(M2Request.engine_run_id == run.id).all()
        result["m2_requests"] = [
            {
                "id": r.id,
                "dc_id": r.dc_id,
                "sku_id": r.sku_id,
                "requested_quantity": r.requested_quantity,
                "urgency": r.urgency,
                "required_by": r.required_by.isoformat() if r.required_by else None,
            }
            for r in m2_requests
        ]
    elif run.engine_type == "m3":
        m3_plans = db.query(M3PlanVersion).filter(M3PlanVersion.engine_run_id == run.id).all()
        result["m3_plans"] = [
            {
                "id": p.id,
                "version_number": p.version_number,
                "plan_status": p.plan_status,
                "score": p.score,
                "is_best": p.is_best,
                "approved_at": p.approved_at.isoformat() if p.approved_at else None,
            }
            for p in m3_plans
        ]

    return result
