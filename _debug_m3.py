"""Check why M3 generated no stops."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from apps.api.app.dependencies.database import SessionLocal
from storage.models import M2Request, EngineRun, M3PlanVersion, WarehouseStockSnapshot, LorryStateItem, LorryStateSnapshot, DCStockItem, DCStockSnapshot

s = SessionLocal()

try:
    last_run = s.query(EngineRun).order_by(EngineRun.id.desc()).first()
    if not last_run:
        print("No engine run.")
        sys.exit(0)
        
    print(f"Last Engine Run ID: {last_run.id}, Status: {last_run.status}")
    
    # Are there M2 requests?
    m2_count = s.query(M2Request).filter(M2Request.engine_run_id == last_run.id).count()
    print(f"M2 Requests for this run: {m2_count}")
    
    # What is the WH Stock effective?
    wh_snap = s.query(WarehouseStockSnapshot).order_by(WarehouseStockSnapshot.id.desc()).first()
    wh_stock = sum(1 for i in wh_snap.items if i.effective_quantity > 0) if wh_snap else 0
    print(f"WH SKUs with effective stock > 0: {wh_stock}")
    
    # What is the lorry state?
    lorry_snap = s.query(LorryStateSnapshot).order_by(LorryStateSnapshot.id.desc()).first()
    avail_lorries = sum(1 for i in lorry_snap.items if i.status == 'available') if lorry_snap else 0
    print(f"Available lorries: {avail_lorries}")

    # Are there M1 Results?
    from storage.models import M1Result
    m1_count = s.query(M1Result).filter(M1Result.engine_run_id == last_run.id).count()
    print(f"M1 Results: {m1_count}")

finally:
    s.close()
