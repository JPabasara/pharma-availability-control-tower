"""M3 Stub — Dispatch Plan Generator with a 2-day lorry horizon."""

from copy import deepcopy


def run(
    m1_results: list[dict],
    m2_requests: list[dict],
    warehouse_stock: dict,
    lorry_state: dict,
    route_graph: list[dict],
) -> list[dict]:
    """Generate 3 candidate plans with day-based lorry runs.

    Each lorry can be used once on Day 1 and once on Day 2.
    Each run may contain up to 2 DC stops.
    """
    wh_stock = {
        item["sku_id"]: {
            "effective": item.get("effective", 0),
            "reefer_required": item.get("reefer_required", False),
            "sku_code": item.get("sku_code", "UNKNOWN"),
        }
        for item in warehouse_stock.get("items", [])
    }
    route_lookup = {
        edge["destination_id"]: {
            "travel_time_hours": edge["travel_time_hours"],
            "cost": edge["cost"],
        }
        for edge in route_graph
        if edge["origin_type"] == "warehouse"
    }

    dc_requests: dict[int, list[dict]] = {}
    for req in m2_requests:
        dc_requests.setdefault(req["dc_id"], []).append({
            **req,
            "remaining_quantity": req["requested_quantity"],
        })

    dc_urgency_scores = _score_dcs(dc_requests)
    slots = _build_slots(lorry_state)

    plan_a = _build_plan(
        version_number=1,
        plan_name="Plan A — Critical DCs First",
        score_base=85,
        ordered_dc_ids=sorted(dc_requests.keys(), key=lambda dc_id: dc_urgency_scores.get(dc_id, 0), reverse=True),
        slots=sorted(slots, key=lambda slot: (slot["dispatch_day"], -slot["capacity_units"])),
        dc_requests=dc_requests,
        wh_stock=wh_stock,
        route_lookup=route_lookup,
        is_best=True,
    )
    plan_b = _build_plan(
        version_number=2,
        plan_name="Plan B — Balanced Distribution",
        score_base=72,
        ordered_dc_ids=list(dc_requests.keys()),
        slots=sorted(slots, key=lambda slot: (-slot["capacity_units"], slot["dispatch_day"])),
        dc_requests=dc_requests,
        wh_stock=wh_stock,
        route_lookup=route_lookup,
        is_best=False,
        round_robin=True,
    )
    plan_c = _build_plan(
        version_number=3,
        plan_name="Plan C — Minimum Cost",
        score_base=64,
        ordered_dc_ids=sorted(
            dc_requests.keys(),
            key=lambda dc_id: route_lookup.get(dc_id, {"cost": 999999})["cost"],
        ),
        slots=sorted(slots, key=lambda slot: (slot["dispatch_day"], slot["capacity_units"])),
        dc_requests=dc_requests,
        wh_stock=wh_stock,
        route_lookup=route_lookup,
        is_best=False,
    )
    return [plan_a, plan_b, plan_c]


def _score_dcs(dc_requests: dict[int, list[dict]]) -> dict[int, float]:
    urgency_score = {"critical": 100, "high": 70, "medium": 40, "low": 10}
    return {
        dc_id: sum(urgency_score.get(request["urgency"], 0) for request in requests)
        for dc_id, requests in dc_requests.items()
    }


def _build_slots(lorry_state: dict) -> list[dict]:
    slots = []
    for lorry in lorry_state.get("lorries", []):
        for dispatch_day in (1, 2):
            if lorry.get(f"day{dispatch_day}_status") == "available":
                slots.append({
                    "lorry_id": lorry["lorry_id"],
                    "registration": lorry["registration"],
                    "lorry_type": lorry["lorry_type"],
                    "capacity_units": lorry["capacity_units"],
                    "dispatch_day": dispatch_day,
                })
    return slots


def _build_plan(
    *,
    version_number: int,
    plan_name: str,
    score_base: float,
    ordered_dc_ids: list[int],
    slots: list[dict],
    dc_requests: dict[int, list[dict]],
    wh_stock: dict[int, dict],
    route_lookup: dict[int, dict],
    is_best: bool,
    round_robin: bool = False,
) -> dict:
    remaining_requests = {
        dc_id: [deepcopy(request) for request in requests]
        for dc_id, requests in dc_requests.items()
    }
    remaining_wh = {
        sku_id: stock["effective"]
        for sku_id, stock in wh_stock.items()
    }
    runs = []
    rr_offset = 0

    for slot in slots:
        run = _build_run_for_slot(
            slot=slot,
            ordered_dc_ids=ordered_dc_ids,
            remaining_requests=remaining_requests,
            remaining_wh=remaining_wh,
            wh_stock=wh_stock,
            route_lookup=route_lookup,
            start_index=rr_offset if round_robin else 0,
        )
        if run:
            runs.append(run)
            if round_robin and ordered_dc_ids:
                rr_offset = (rr_offset + 1) % len(ordered_dc_ids)

    flat_stops = []
    for run in runs:
        for stop in run["stops"]:
            flat_stops.append({
                "lorry_id": run["lorry_id"],
                "registration": run["registration"],
                "lorry_type": run["lorry_type"],
                "dispatch_day": run["dispatch_day"],
                **stop,
            })

    total_items_loaded = sum(
        item["quantity"]
        for run in runs
        for stop in run["stops"]
        for item in stop["items"]
    )
    return {
        "version_number": version_number,
        "plan_name": plan_name,
        "score": round(score_base + min(18, len(runs) * 1.5 + len(flat_stops)), 1),
        "is_best": is_best,
        "runs": runs,
        "stops": flat_stops,
        "summary": {
            "total_runs": len(runs),
            "total_stops": len(flat_stops),
            "total_items_loaded": total_items_loaded,
        },
    }


def _build_run_for_slot(
    *,
    slot: dict,
    ordered_dc_ids: list[int],
    remaining_requests: dict[int, list[dict]],
    remaining_wh: dict[int, int],
    wh_stock: dict[int, dict],
    route_lookup: dict[int, dict],
    start_index: int,
) -> dict | None:
    stops = []
    remaining_capacity = slot["capacity_units"]
    ordered = ordered_dc_ids[start_index:] + ordered_dc_ids[:start_index]

    for dc_id in ordered:
        if len(stops) >= 2 or remaining_capacity <= 0:
            break

        stop_items = _assign_stop_items(
            lorry_type=slot["lorry_type"],
            dc_id=dc_id,
            requests=remaining_requests.get(dc_id, []),
            remaining_wh=remaining_wh,
            wh_stock=wh_stock,
            remaining_capacity=remaining_capacity,
        )
        if not stop_items:
            continue

        route = route_lookup.get(dc_id, {"travel_time_hours": 6.0, "cost": 15000})
        loaded = sum(item["quantity"] for item in stop_items)
        remaining_capacity -= loaded
        stops.append({
            "dc_id": dc_id,
            "stop_sequence": len(stops) + 1,
            "travel_time_hours": route["travel_time_hours"],
            "items": stop_items,
        })

    if not stops:
        return None

    return {
        "lorry_id": slot["lorry_id"],
        "registration": slot["registration"],
        "lorry_type": slot["lorry_type"],
        "capacity_units": slot["capacity_units"],
        "dispatch_day": slot["dispatch_day"],
        "stops": stops,
    }


def _assign_stop_items(
    *,
    lorry_type: str,
    dc_id: int,
    requests: list[dict],
    remaining_wh: dict[int, int],
    wh_stock: dict[int, dict],
    remaining_capacity: int,
) -> list[dict]:
    items = []
    loaded = 0

    for request in requests:
        if request["remaining_quantity"] <= 0 or loaded >= remaining_capacity:
            continue

        sku_info = wh_stock.get(request["sku_id"], {})
        sku_requires_reefer = sku_info.get("reefer_required", False)
        if lorry_type == "reefer" and not sku_requires_reefer:
            continue
        if lorry_type == "normal" and sku_requires_reefer:
            continue

        available_wh = remaining_wh.get(request["sku_id"], 0)
        qty = min(request["remaining_quantity"], available_wh, remaining_capacity - loaded)
        if qty <= 0:
            continue

        request["remaining_quantity"] -= qty
        remaining_wh[request["sku_id"]] = max(0, available_wh - qty)
        loaded += qty
        items.append({
            "sku_id": request["sku_id"],
            "sku_code": sku_info.get("sku_code", request.get("sku_code", "UNKNOWN")),
            "quantity": qty,
            "dc_id": dc_id,
        })

    return items
