"""Mock ETA endpoints — refresh and view vessel ETAs.

Routes:
    POST /api/v1/mock/eta/refresh/{vessel_id}   — refresh ETA for a vessel
    GET  /api/v1/mock/eta/latest                — all latest ETAs
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from apps.api.app.dependencies.database import get_db
from integrations.inbound.eta_provider import provider as eta_provider
from storage.models import Vessel

router = APIRouter(prefix="/api/v1/mock/eta", tags=["mock-eta"])


@router.post("/refresh/{vessel_id}")
def refresh_eta(vessel_id: int, db: Session = Depends(get_db)):
    """Refresh the mock ETA for a specific vessel.

    Generates a new random ETA (current time + 4–48h offset) and persists it.
    """
    # Validate vessel exists
    vessel = db.query(Vessel).filter(Vessel.id == vessel_id).first()
    if not vessel:
        raise HTTPException(status_code=404, detail=f"Vessel {vessel_id} not found.")

    result = eta_provider.refresh_eta(db, vessel_id)
    return {
        "success": True,
        "message": f"ETA refreshed for vessel {vessel.name}.",
        **result,
    }


@router.get("/latest")
def get_latest_etas(db: Session = Depends(get_db)):
    """Get the latest ETAs for all vessels with active manifests."""
    etas = eta_provider.get_all_active_etas(db)
    return {"etas": etas, "count": len(etas)}
