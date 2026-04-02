"""Verify all FastAPI routes import and register correctly."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from apps.api.app.main import app

print("=" * 60)
print("FastAPI Route Verification")
print("=" * 60)
print()

routes = []
for route in app.routes:
    if hasattr(route, "methods"):
        for method in route.methods:
            if method != "HEAD":
                routes.append((method, route.path))

routes.sort(key=lambda value: (value[1], value[0]))

for method, path in routes:
    print(f"  {method:6s} {path}")

print()
print(f"Total endpoints: {len(routes)}")
print()

expected = [
    ("GET", "/"),
    ("GET", "/api/v1/inputs/manifests"),
    ("GET", "/api/v1/inputs/manifests/{manifest_id}"),
    ("GET", "/api/v1/inputs/warehouse-stock"),
    ("GET", "/api/v1/inputs/dc-stock"),
    ("GET", "/api/v1/inputs/dc-stock/{dc_id}"),
    ("GET", "/api/v1/inputs/sales-history"),
    ("GET", "/api/v1/inputs/lorry-state"),
    ("GET", "/api/v1/inputs/etas"),
    ("POST", "/api/v1/inputs/refresh-all"),
    ("POST", "/api/v1/inputs/refresh/{family}"),
    ("POST", "/api/v1/orchestration/generate-plan"),
    ("GET", "/api/v1/orchestration/runs"),
    ("GET", "/api/v1/orchestration/runs/{run_id}"),
    ("GET", "/api/v1/planner/m1-results/{run_id}"),
    ("GET", "/api/v1/planner/m2-requests/{run_id}"),
    ("GET", "/api/v1/planner/m3-plans/{run_id}"),
    ("GET", "/api/v1/planner/m3-plans/{run_id}/{version_id}"),
    ("POST", "/api/v1/planner/approve/{plan_version_id}"),
    ("POST", "/api/v1/planner/reject/{plan_version_id}"),
    ("POST", "/api/v1/planner/override/{plan_version_id}"),
    ("POST", "/api/v1/demo-operations/manifests/upload"),
    ("POST", "/api/v1/demo-operations/manifests/{manifest_id}/arrive"),
    ("POST", "/api/v1/demo-operations/dc-sales"),
    ("GET", "/api/v1/demo-operations/lorries/horizon"),
    ("POST", "/api/v1/demo-operations/lorries/{lorry_id}/availability"),
    ("GET", "/api/v1/demo-operations/execution/open-stops"),
    ("POST", "/api/v1/demo-operations/execution/stops/{plan_stop_id}/arrive"),
    ("GET", "/api/v1/demo-state/reservations"),
    ("GET", "/api/v1/demo-state/transfers"),
    ("GET", "/api/v1/demo-state/stock-summary"),
    ("GET", "/api/v1/demo-state/arrival-events"),
    ("GET", "/api/v1/reports/approved-plans"),
    ("GET", "/api/v1/reports/audit-trail"),
    ("POST", "/api/v1/mock/eta/refresh/{vessel_id}"),
    ("GET", "/api/v1/mock/eta/latest"),
    ("GET", "/api/v1/dashboard/summary"),
]

missing = [(method, path) for method, path in expected if (method, path) not in routes]

if missing:
    print("MISSING ENDPOINTS:")
    for method, path in missing:
        print(f"  X {method} {path}")
    print()
    sys.exit(1)

print(f"OK: All {len(expected)} expected endpoints are registered.")
print()
print("VERIFICATION PASSED")
