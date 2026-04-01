"""Hosted demo operations endpoints."""

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from apps.api.app.dependencies.database import get_db
from apps.api.app.demo_operations import service

router = APIRouter(prefix="/api/v1/demo-operations", tags=["demo-operations"])


class DcSaleRequest(BaseModel):
    dc_id: int
    sku_id: int
    quantity: int
    actor: str = "demo-ops"


class LorryAvailabilityRequest(BaseModel):
    status: str
    actor: str = "demo-ops"


@router.post("/manifests/upload")
async def upload_manifest(
    manifest_name: str = Form(...),
    vessel_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    result = service.upload_manifest(
        db,
        manifest_name=manifest_name,
        vessel_id=vessel_id,
        csv_bytes=await file.read(),
    )
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@router.post("/manifests/{manifest_id}/arrive")
def arrive_manifest(manifest_id: int, db: Session = Depends(get_db)):
    result = service.arrive_manifest(db, manifest_id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@router.post("/dc-sales")
def post_dc_sale(body: DcSaleRequest, db: Session = Depends(get_db)):
    result = service.post_dc_sale(
        db,
        dc_id=body.dc_id,
        sku_id=body.sku_id,
        quantity=body.quantity,
        actor=body.actor,
    )
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@router.get("/lorries/horizon")
def get_lorry_horizon(db: Session = Depends(get_db)):
    contract = service.get_lorry_horizon(db)
    if not contract:
        raise HTTPException(status_code=404, detail="No lorry state snapshot found.")
    return contract


@router.post("/lorries/{lorry_id}/availability")
def set_lorry_availability(
    lorry_id: int,
    body: LorryAvailabilityRequest,
    db: Session = Depends(get_db),
):
    result = service.set_lorry_availability(
        db,
        lorry_id=lorry_id,
        status=body.status,
        actor=body.actor,
    )
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@router.get("/execution/open-stops")
def get_open_execution_stops(db: Session = Depends(get_db)):
    stops = service.get_open_execution_stops(db)
    return {"open_stops": stops, "count": len(stops)}


@router.post("/execution/stops/{plan_stop_id}/arrive")
def arrive_stop(plan_stop_id: int, db: Session = Depends(get_db)):
    result = service.arrive_stop(db, plan_stop_id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result
