"""Quick DB state check."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from apps.api.app.dependencies.database import SessionLocal
from storage.models import ManifestSnapshot, DemoTransfer

s = SessionLocal()
try:
    manifests = s.query(ManifestSnapshot).all()
    transfers = s.query(DemoTransfer).all()
    active = sum(1 for m in manifests if m.status == "active")
    in_transit = sum(1 for t in transfers if t.status == "in_transit")
    print(f"Manifests: {len(manifests)} total, {active} active")
    print(f"Transfers: {len(transfers)} total, {in_transit} in_transit")
finally:
    s.close()
