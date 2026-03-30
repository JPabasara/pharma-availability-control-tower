"""Quick functional test for all Macro-Phase A components."""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

# Test M2 stub
print("=" * 60)
print("Testing M2 Stub (DC Replenishment Requests)")
print("=" * 60)

from apps.api.app.orchestration.stubs.m2_stub import run as m2_run

dc_stock = [
    {
        "dc_id": 3, "dc_code": "DC-GLE",
        "items": [
            {"sku_id": 1, "sku_code": "AMX-500", "effective": 50},
            {"sku_id": 7, "sku_code": "PAR-500", "effective": 60},
        ],
    }
]
forecasts = [
    {"dc_id": 3, "sku_id": 1, "sku_code": "AMX-500", "dc_code": "DC-GLE",
     "sku_name": "Amoxicillin", "forecast_48h": 200, "daily_avg": 100},
    {"dc_id": 3, "sku_id": 7, "sku_code": "PAR-500", "dc_code": "DC-GLE",
     "sku_name": "Paracetamol", "forecast_48h": 300, "daily_avg": 150},
]

m2_out = m2_run(dc_stock, forecasts)
print(f"  M2 requests generated: {len(m2_out)}")
for r in m2_out:
    print(f"    DC {r['dc_code']} SKU {r['sku_code']}: qty={r['requested_quantity']}, "
          f"urgency={r['urgency']}, coverage={r['hours_coverage']}h")
print()

# Test M1 stub
print("=" * 60)
print("Testing M1 Stub (Manifest Priority Scoring)")
print("=" * 60)

from apps.api.app.orchestration.stubs.m1_stub import run as m1_run

lines = [
    {"manifest_line_id": 1, "sku_id": 1, "sku_code": "AMX-500",
     "quantity": 2000, "reefer_required": False},
    {"manifest_line_id": 2, "sku_id": 3, "sku_code": "INS-100",
     "quantity": 800, "reefer_required": True},
]
wh = {"items": [{"sku_id": 1, "effective": 8000}, {"sku_id": 3, "effective": 3000}]}

m1_out = m1_run(lines, wh, m2_out, {}, [{"hours_until_arrival": 6}])
print(f"  M1 results: {len(m1_out)}")
for r in m1_out:
    print(f"    SKU {r['sku_code']}: score={r['priority_score']}, "
          f"band={r['priority_band']}, reefer={r['reefer_required']}")
print()

# Test M3 stub
print("=" * 60)
print("Testing M3 Stub (Dispatch Plan Generation)")
print("=" * 60)

from apps.api.app.orchestration.stubs.m3_stub import run as m3_run

lorries = {
    "lorries": [
        {"lorry_id": 1, "registration": "LR-N-001", "lorry_type": "normal",
         "capacity_units": 500, "status": "available"},
        {"lorry_id": 6, "registration": "LR-R-001", "lorry_type": "reefer",
         "capacity_units": 350, "status": "available"},
    ]
}
wh_full = {
    "items": [
        {"sku_id": 1, "effective": 8000, "reefer_required": False, "sku_code": "AMX-500"},
        {"sku_id": 7, "effective": 12000, "reefer_required": False, "sku_code": "PAR-500"},
    ]
}
routes = [
    {"origin_type": "warehouse", "origin_id": 1, "destination_type": "dc",
     "destination_id": 3, "travel_time_hours": 3.5, "cost": 9000},
]

m3_out = m3_run(m1_out, m2_out, wh_full, lorries, routes)
print(f"  M3 plans generated: {len(m3_out)}")
for p in m3_out:
    total_items = sum(sum(i["quantity"] for i in s["items"]) for s in p["stops"])
    print(f"    {p['plan_name']}: score={p['score']}, is_best={p['is_best']}, "
          f"stops={len(p['stops'])}, items_loaded={total_items}")
    for s in p["stops"]:
        item_total = sum(i["quantity"] for i in s["items"])
        print(f"      -> {s['registration']} ({s['lorry_type']}) "
              f"to DC {s['dc_id']}: {item_total} units")
print()

# Test engine bridge
print("=" * 60)
print("Testing Engine Bridge (MODE=stub)")
print("=" * 60)
from apps.api.app.orchestration.engine_bridge import get_engine_mode
print(f"  Engine mode: {get_engine_mode()}")
print()

print("=" * 60)
print("ALL MACRO-PHASE A TESTS PASSED!")
print("=" * 60)
