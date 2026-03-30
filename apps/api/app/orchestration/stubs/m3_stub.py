"""M3 Stub — Dispatch Plan Generator.

Generates 3 candidate dispatch plans:
  Plan A: Prioritize critical DCs (best plan, marked is_best)
  Plan B: Balanced distribution across all DCs
  Plan C: Minimize travel cost

Constraints enforced:
  - 1 trip per lorry
  - Max 2 stops per trip
  - Reefer lorries → reefer SKUs only
  - Normal lorries → normal SKUs only
  - Load per lorry ≤ capacity_units
"""

from datetime import datetime, timedelta, timezone


def run(
    m1_results: list[dict],
    m2_requests: list[dict],
    warehouse_stock: dict,
    lorry_state: dict,
    route_graph: list[dict],
) -> list[dict]:
    """Run M3 stub to generate 3 candidate dispatch plans.

    Args:
        m1_results: M1 priority-scored manifest lines
        m2_requests: M2 DC replenishment requests [{dc_id, sku_id, requested_quantity, urgency}]
        warehouse_stock: WH stock contract {items: [{sku_id, effective, reefer_required}]}
        lorry_state: {lorries: [{lorry_id, registration, lorry_type, capacity_units, status}]}
        route_graph: [{origin_type, origin_id, destination_type, destination_id, travel_time_hours, cost}]

    Returns:
        List of 3 plan versions:
        [{version_number, plan_name, score, is_best,
          stops: [{lorry_id, registration, dc_id, dc_code, stop_sequence,
                   travel_time_hours, items: [{sku_id, sku_code, quantity}]}]}]
    """
    # Separate available lorries by type
    available_lorries = [
        l for l in lorry_state.get("lorries", []) if l["status"] == "available"
    ]
    normal_lorries = [l for l in available_lorries if l["lorry_type"] == "normal"]
    reefer_lorries = [l for l in available_lorries if l["lorry_type"] == "reefer"]

    # Build WH effective stock lookup
    wh_stock: dict[int, dict] = {}
    if warehouse_stock and "items" in warehouse_stock:
        for item in warehouse_stock["items"]:
            wh_stock[item["sku_id"]] = {
                "effective": item["effective"],
                "reefer_required": item.get("reefer_required", False),
                "sku_code": item.get("sku_code", "UNKNOWN"),
            }

    # Build route lookup: dc_id → {travel_time_hours, cost} from warehouse
    route_lookup: dict[int, dict] = {}
    for edge in route_graph:
        if edge["origin_type"] == "warehouse":
            route_lookup[edge["destination_id"]] = {
                "travel_time_hours": edge["travel_time_hours"],
                "cost": edge["cost"],
            }

    # Group M2 requests by DC and separate by reefer
    dc_requests: dict[int, list[dict]] = {}
    for req in m2_requests:
        dc_id = req["dc_id"]
        dc_requests.setdefault(dc_id, []).append(req)

    # Score DCs by urgency for prioritization
    urgency_score = {"critical": 100, "high": 70, "medium": 40, "low": 10}
    dc_urgency_scores: dict[int, float] = {}
    for dc_id, reqs in dc_requests.items():
        dc_urgency_scores[dc_id] = sum(
            urgency_score.get(r["urgency"], 0) for r in reqs
        )

    # Generate 3 plans
    plans = [
        _generate_plan_a(
            dc_requests, dc_urgency_scores, normal_lorries, reefer_lorries,
            wh_stock, route_lookup
        ),
        _generate_plan_b(
            dc_requests, dc_urgency_scores, normal_lorries, reefer_lorries,
            wh_stock, route_lookup
        ),
        _generate_plan_c(
            dc_requests, dc_urgency_scores, normal_lorries, reefer_lorries,
            wh_stock, route_lookup
        ),
    ]

    return plans


def _assign_items_to_lorry(
    lorry: dict,
    dc_reqs: list[dict],
    wh_stock: dict[int, dict],
    is_reefer: bool,
) -> list[dict]:
    """Assign items from requests to a lorry respecting capacity and type constraints."""
    capacity = lorry["capacity_units"]
    loaded = 0
    items = []

    for req in dc_reqs:
        sku_id = req["sku_id"]
        sku_info = wh_stock.get(sku_id, {})
        sku_reefer = sku_info.get("reefer_required", False)

        # Enforce reefer/normal segregation
        if is_reefer and not sku_reefer:
            continue
        if not is_reefer and sku_reefer:
            continue

        available = sku_info.get("effective", 0)
        requested = req["requested_quantity"]
        can_load = min(requested, available, capacity - loaded)

        if can_load > 0:
            items.append({
                "sku_id": sku_id,
                "sku_code": sku_info.get("sku_code", req.get("sku_code", "UNKNOWN")),
                "quantity": can_load,
            })
            loaded += can_load

        if loaded >= capacity:
            break

    return items


def _generate_plan_a(
    dc_requests, dc_urgency_scores, normal_lorries, reefer_lorries,
    wh_stock, route_lookup
) -> dict:
    """Plan A: Prioritize critical DCs — allocate largest lorries to most urgent DCs."""
    stops = []
    used_lorries = set()

    # Sort DCs by urgency score descending
    sorted_dcs = sorted(dc_urgency_scores.keys(), key=lambda d: dc_urgency_scores[d], reverse=True)

    # Sort lorries by capacity descending
    sorted_normal = sorted(normal_lorries, key=lambda l: l["capacity_units"], reverse=True)
    sorted_reefer = sorted(reefer_lorries, key=lambda l: l["capacity_units"], reverse=True)

    normal_idx = 0
    reefer_idx = 0
    stop_seq = 1

    for dc_id in sorted_dcs:
        reqs = dc_requests.get(dc_id, [])
        if not reqs:
            continue

        # Separate requests by reefer type
        normal_reqs = [r for r in reqs if not wh_stock.get(r["sku_id"], {}).get("reefer_required", False)]
        reefer_reqs = [r for r in reqs if wh_stock.get(r["sku_id"], {}).get("reefer_required", False)]

        route = route_lookup.get(dc_id, {"travel_time_hours": 6.0, "cost": 15000})

        # Assign normal lorry if needed
        if normal_reqs and normal_idx < len(sorted_normal):
            lorry = sorted_normal[normal_idx]
            if lorry["lorry_id"] not in used_lorries:
                items = _assign_items_to_lorry(lorry, normal_reqs, wh_stock, False)
                if items:
                    stops.append({
                        "lorry_id": lorry["lorry_id"],
                        "registration": lorry["registration"],
                        "lorry_type": "normal",
                        "dc_id": dc_id,
                        "stop_sequence": stop_seq,
                        "travel_time_hours": route["travel_time_hours"],
                        "items": items,
                    })
                    used_lorries.add(lorry["lorry_id"])
                    normal_idx += 1
                    stop_seq += 1

        # Assign reefer lorry if needed
        if reefer_reqs and reefer_idx < len(sorted_reefer):
            lorry = sorted_reefer[reefer_idx]
            if lorry["lorry_id"] not in used_lorries:
                items = _assign_items_to_lorry(lorry, reefer_reqs, wh_stock, True)
                if items:
                    stops.append({
                        "lorry_id": lorry["lorry_id"],
                        "registration": lorry["registration"],
                        "lorry_type": "reefer",
                        "dc_id": dc_id,
                        "stop_sequence": stop_seq,
                        "travel_time_hours": route["travel_time_hours"],
                        "items": items,
                    })
                    used_lorries.add(lorry["lorry_id"])
                    reefer_idx += 1
                    stop_seq += 1

    total_items = sum(sum(i["quantity"] for i in s["items"]) for s in stops)

    return {
        "version_number": 1,
        "plan_name": "Plan A — Critical DCs First",
        "score": round(85 + min(15, len(stops) * 2), 1),
        "is_best": True,
        "stops": stops,
        "summary": {
            "total_lorries": len(used_lorries),
            "total_stops": len(stops),
            "total_items_loaded": total_items,
        },
    }


def _generate_plan_b(
    dc_requests, dc_urgency_scores, normal_lorries, reefer_lorries,
    wh_stock, route_lookup
) -> dict:
    """Plan B: Balanced distribution — spread lorries evenly across all requesting DCs."""
    stops = []
    used_lorries = set()

    # Distribute round-robin across DCs
    all_dcs = list(dc_requests.keys())
    normal_pool = list(normal_lorries)
    reefer_pool = list(reefer_lorries)
    stop_seq = 1

    for i, dc_id in enumerate(all_dcs):
        reqs = dc_requests.get(dc_id, [])
        route = route_lookup.get(dc_id, {"travel_time_hours": 6.0, "cost": 15000})

        normal_reqs = [r for r in reqs if not wh_stock.get(r["sku_id"], {}).get("reefer_required", False)]
        reefer_reqs = [r for r in reqs if wh_stock.get(r["sku_id"], {}).get("reefer_required", False)]

        # Try to assign a normal lorry
        for lorry in normal_pool:
            if lorry["lorry_id"] not in used_lorries and normal_reqs:
                items = _assign_items_to_lorry(lorry, normal_reqs, wh_stock, False)
                if items:
                    stops.append({
                        "lorry_id": lorry["lorry_id"],
                        "registration": lorry["registration"],
                        "lorry_type": "normal",
                        "dc_id": dc_id,
                        "stop_sequence": stop_seq,
                        "travel_time_hours": route["travel_time_hours"],
                        "items": items,
                    })
                    used_lorries.add(lorry["lorry_id"])
                    stop_seq += 1
                    break

        # Try to assign a reefer lorry
        for lorry in reefer_pool:
            if lorry["lorry_id"] not in used_lorries and reefer_reqs:
                items = _assign_items_to_lorry(lorry, reefer_reqs, wh_stock, True)
                if items:
                    stops.append({
                        "lorry_id": lorry["lorry_id"],
                        "registration": lorry["registration"],
                        "lorry_type": "reefer",
                        "dc_id": dc_id,
                        "stop_sequence": stop_seq,
                        "travel_time_hours": route["travel_time_hours"],
                        "items": items,
                    })
                    used_lorries.add(lorry["lorry_id"])
                    stop_seq += 1
                    break

    total_items = sum(sum(i["quantity"] for i in s["items"]) for s in stops)

    return {
        "version_number": 2,
        "plan_name": "Plan B — Balanced Distribution",
        "score": round(70 + min(10, len(stops) * 1.5), 1),
        "is_best": False,
        "stops": stops,
        "summary": {
            "total_lorries": len(used_lorries),
            "total_stops": len(stops),
            "total_items_loaded": total_items,
        },
    }


def _generate_plan_c(
    dc_requests, dc_urgency_scores, normal_lorries, reefer_lorries,
    wh_stock, route_lookup
) -> dict:
    """Plan C: Minimize travel cost — serve cheapest-to-reach DCs first."""
    stops = []
    used_lorries = set()

    # Sort DCs by travel cost ascending
    dcs_with_cost = []
    for dc_id in dc_requests.keys():
        route = route_lookup.get(dc_id, {"travel_time_hours": 6.0, "cost": 15000})
        dcs_with_cost.append((dc_id, route["cost"]))
    dcs_with_cost.sort(key=lambda x: x[1])

    normal_pool = list(normal_lorries)
    reefer_pool = list(reefer_lorries)
    stop_seq = 1

    for dc_id, cost in dcs_with_cost:
        reqs = dc_requests.get(dc_id, [])
        route = route_lookup.get(dc_id, {"travel_time_hours": 6.0, "cost": 15000})

        normal_reqs = [r for r in reqs if not wh_stock.get(r["sku_id"], {}).get("reefer_required", False)]
        reefer_reqs = [r for r in reqs if wh_stock.get(r["sku_id"], {}).get("reefer_required", False)]

        # Assign smallest-capacity lorry that fits (to minimize waste)
        if normal_reqs:
            eligible = [l for l in normal_pool if l["lorry_id"] not in used_lorries]
            eligible.sort(key=lambda l: l["capacity_units"])
            for lorry in eligible:
                items = _assign_items_to_lorry(lorry, normal_reqs, wh_stock, False)
                if items:
                    stops.append({
                        "lorry_id": lorry["lorry_id"],
                        "registration": lorry["registration"],
                        "lorry_type": "normal",
                        "dc_id": dc_id,
                        "stop_sequence": stop_seq,
                        "travel_time_hours": route["travel_time_hours"],
                        "items": items,
                    })
                    used_lorries.add(lorry["lorry_id"])
                    stop_seq += 1
                    break

        if reefer_reqs:
            eligible = [l for l in reefer_pool if l["lorry_id"] not in used_lorries]
            eligible.sort(key=lambda l: l["capacity_units"])
            for lorry in eligible:
                items = _assign_items_to_lorry(lorry, reefer_reqs, wh_stock, True)
                if items:
                    stops.append({
                        "lorry_id": lorry["lorry_id"],
                        "registration": lorry["registration"],
                        "lorry_type": "reefer",
                        "dc_id": dc_id,
                        "stop_sequence": stop_seq,
                        "travel_time_hours": route["travel_time_hours"],
                        "items": items,
                    })
                    used_lorries.add(lorry["lorry_id"])
                    stop_seq += 1
                    break

    total_items = sum(sum(i["quantity"] for i in s["items"]) for s in stops)

    return {
        "version_number": 3,
        "plan_name": "Plan C — Minimum Cost",
        "score": round(60 + min(10, len(stops)), 1),
        "is_best": False,
        "stops": stops,
        "summary": {
            "total_lorries": len(used_lorries),
            "total_stops": len(stops),
            "total_items_loaded": total_items,
        },
    }
