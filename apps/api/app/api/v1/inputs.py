"""Input snapshot endpoints — read-only access to all system inputs.

Routes:
    GET /api/v1/inputs/manifests             — all active manifests
    GET /api/v1/inputs/manifests/{id}        — specific manifest
    GET /api/v1/inputs/warehouse-stock       — latest effective WH stock
    GET /api/v1/inputs/dc-stock              — latest effective DC stock (all DCs)
    GET /api/v1/inputs/dc-stock/{dc_id}      — specific DC stock
    GET /api/v1/inputs/sales-history         — sales history with 48h forecasts
    GET /api/v1/inputs/lorry-state           — current lorry availability
    GET /api/v1/inputs/etas                  — all active ETAs
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from apps.api.app.dependencies.database import get_db
from integrations.inbound.manifest_reader import reader as manifest_reader
from integrations.inbound.warehouse_stock_reader import reader as wh_reader
from integrations.inbound.dc_stock_reader import reader as dc_reader
from integrations.inbound.sales_history_reader import reader as sales_reader
from integrations.inbound.lorry_state_reader import reader as lorry_reader
from integrations.inbound.eta_provider import provider as eta_provider

router = APIRouter(prefix="/api/v1/inputs", tags=["inputs"])


@router.get("/manifests")
def get_manifests(db: Session = Depends(get_db)):
    """Get all active vessel manifests with line items."""
    contracts = manifest_reader.get_all_active_contracts(db)
    return {"manifests": contracts, "count": len(contracts)}


@router.get("/manifests/{manifest_id}")
def get_manifest_by_id(manifest_id: int, db: Session = Depends(get_db)):
    """Get a specific manifest snapshot by ID."""
    snapshot = manifest_reader.get_by_id(db, manifest_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail=f"Manifest snapshot {manifest_id} not found.")
    return manifest_reader.to_contract(db, snapshot)


@router.get("/warehouse-stock")
def get_warehouse_stock(db: Session = Depends(get_db)):
    """Get latest effective warehouse stock (Physical − Reserved)."""
    contract = wh_reader.get_latest_contract(db)
    if not contract:
        raise HTTPException(status_code=404, detail="No warehouse stock snapshot found.")
    return contract


@router.get("/dc-stock")
def get_all_dc_stock(db: Session = Depends(get_db)):
    """Get latest effective DC stock for all DCs (Physical + In-Transit)."""
    contracts = dc_reader.get_all_latest_contracts(db)
    return {"dcs": contracts, "count": len(contracts)}


@router.get("/dc-stock/{dc_id}")
def get_dc_stock(dc_id: int, db: Session = Depends(get_db)):
    """Get latest effective stock for a specific DC."""
    contract = dc_reader.get_dc_contract(db, dc_id)
    if not contract:
        raise HTTPException(status_code=404, detail=f"No stock snapshot found for DC {dc_id}.")
    return contract


@router.get("/sales-history")
def get_sales_history(db: Session = Depends(get_db)):
    """Get sales history with 48-hour demand forecasts per DC per SKU."""
    forecasts = sales_reader.to_contract(db)
    return {"forecasts": forecasts, "count": len(forecasts)}


@router.get("/lorry-state")
def get_lorry_state(db: Session = Depends(get_db)):
    """Get current lorry availability from latest snapshot."""
    contract = lorry_reader.get_latest_contract(db)
    if not contract:
        raise HTTPException(status_code=404, detail="No lorry state snapshot found.")
    return contract


@router.get("/etas")
def get_etas(db: Session = Depends(get_db)):
    """Get latest ETAs for all vessels with active manifests."""
    etas = eta_provider.get_all_active_etas(db)
    return {"etas": etas, "count": len(etas)}
