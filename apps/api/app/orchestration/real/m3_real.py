"""M3 Real Engine — OR-Tools Candidate Dispatch Planner.

Solves the dispatch optimization using Google OR-Tools and generates
3 candidate plan variants as required by the planner workflow.

Adapter responsibilities:
1. Convert live DB-backed inputs into solver-compatible data structures
2. Run OR-Tools SCIP solver with different objective weightings
3. Package solutions into the planner contract (version/run/stop/item hierarchy)
4. Emit solver trace metadata for debugging

Candidate Plan Strategy (from Integrate-plan.md):
- Plan A: urgency-maximizing variant (marked is_best)
- Plan B: balanced coverage variant (spread across DCs)
- Plan C: cost-aware variant (minimize travel cost)
"""

import logging
from copy import deepcopy
from typing import Optional

logger = logging.getLogger(__name__)

MAX_STOPS_PER_LORRY = 2

# ═══════════════════════════════════════════════════════════════════════
# INPUT NORMALIZATION — live DB contracts → solver inputs
# ═══════════════════════════════════════════════════════════════════════


def _normalize_inputs(
    m2_requests: list[dict],
    warehouse_stock: dict,
    lorry_state: dict,
    route_graph: list[dict],
    sku_metadata: dict,
) -> tuple[list[dict], dict, list[dict], dict, list[dict]]:
    """Convert platform contracts into solver-compatible data structures.

    Returns: (requests, wh_stock, lorries, route_lookup, lorry_slots)
    """
    # Aggregate M2 requests by (dc_id, sku_id)
    agg: dict[tuple[int, int], dict] = {}
    for req in m2_requests:
        key = (req["dc_id"], req["sku_id"])
        if key not in agg:
            agg[key] = {
                "dc_id": req["dc_id"],
                "sku_id": req["sku_id"],
                "sku_code": req.get("sku_code", "UNKNOWN"),
                "category": req.get("category", ""),
                "requested_quantity": 0,
                "urgency_score": 0,
                "urgency": req.get("urgency", "low"),
            }
        agg[key]["requested_quantity"] += req["requested_quantity"]
        # Use max urgency
        urgency_map = {"critical": 100, "high": 70, "medium": 40, "low": 10}
        current_score = urgency_map.get(agg[key]["urgency"], 10)
        new_score = urgency_map.get(req.get("urgency", "low"), 10)
        if "urgency_score" in req:
            new_score = max(new_score, req["urgency_score"])
        if new_score > current_score:
            agg[key]["urgency_score"] = new_score
        else:
            agg[key]["urgency_score"] = max(agg[key]["urgency_score"], current_score)

    requests = [r for r in agg.values() if r["requested_quantity"] > 0]

    # Warehouse stock
    wh_stock = {}
    for item in warehouse_stock.get("items", []):
        sku_id = item["sku_id"]
        sku_meta = sku_metadata.get(sku_id, {})
        wh_stock[sku_id] = {
            "effective": item.get("effective", 0),
            "reefer_required": item.get("reefer_required", sku_meta.get("reefer_required", False)),
            "sku_code": item.get("sku_code", sku_meta.get("code", "UNKNOWN")),
            "category": sku_meta.get("category", ""),
        }

    # Route lookup: destination_id → {travel_time_hours, cost}
    route_lookup = {}
    for edge in route_graph:
        if edge["origin_type"] == "warehouse":
            route_lookup[edge["destination_id"]] = {
                "travel_time_hours": edge["travel_time_hours"],
                "cost": edge["cost"],
            }

    # Build lorry day-slots
    lorries = lorry_state.get("lorries", [])
    slots = []
    for lorry in lorries:
        for day in (1, 2):
            status_key = f"day{day}_status"
            if lorry.get(status_key) == "available":
                slots.append({
                    "lorry_id": lorry["lorry_id"],
                    "registration": lorry.get("registration", "UNKNOWN"),
                    "lorry_type": lorry.get("lorry_type", "normal"),
                    "capacity_units": lorry.get("capacity_units", 1000),
                    "dispatch_day": day,
                })

    return requests, wh_stock, lorries, route_lookup, slots


# ═══════════════════════════════════════════════════════════════════════
# OR-TOOLS SOLVER
# ═══════════════════════════════════════════════════════════════════════


def _solve_dispatch(
    requests: list[dict],
    wh_stock: dict,
    slots: list[dict],
    route_lookup: dict,
    objective_mode: str = "urgency",
) -> tuple[Optional[list[dict]], float, dict]:
    """Solve the dispatch optimization problem.

    Args:
        objective_mode: 'urgency' (max urgency), 'balanced' (spread across DCs), 'cost' (min cost)

    Returns: (runs, objective_value, solver_trace)
    """
    try:
        from ortools.linear_solver import pywraplp
    except ImportError:
        logger.error("OR-Tools not available, falling back to heuristic")
        return _heuristic_solve(requests, wh_stock, slots, route_lookup, objective_mode)

    solver = pywraplp.Solver.CreateSolver('SCIP')
    if not solver:
        logger.error("Could not create SCIP solver, falling back to heuristic")
        return _heuristic_solve(requests, wh_stock, slots, route_lookup, objective_mode)

    if not requests or not slots:
        return [], 0.0, {"status": "empty_inputs"}

    DCs = list(set(r["dc_id"] for r in requests))
    SKUs = list(wh_stock.keys())

    # Decision variables
    # x[s, d, k] = quantity of SKU k loaded onto slot s for DC d
    x = {}
    for s_idx, slot in enumerate(slots):
        for d in DCs:
            for k in SKUs:
                x[(s_idx, d, k)] = solver.IntVar(0, solver.infinity(), f'x_{s_idx}_{d}_{k}')

    # y[s, d] = binary: slot s visits DC d
    y = {}
    for s_idx in range(len(slots)):
        for d in DCs:
            y[(s_idx, d)] = solver.IntVar(0, 1, f'y_{s_idx}_{d}')

    # ── Constraints ──────────────────────────────────────────────────

    # 1. Max 2 stops per slot
    for s_idx in range(len(slots)):
        solver.Add(sum(y[(s_idx, d)] for d in DCs) <= MAX_STOPS_PER_LORRY)

    # 2. Logic link: items → visit
    for s_idx, slot in enumerate(slots):
        for d in DCs:
            items_for_d = sum(x[(s_idx, d, k)] for k in SKUs)
            solver.Add(items_for_d <= slot["capacity_units"] * y[(s_idx, d)])

    # 3. Capacity + cold chain
    for s_idx, slot in enumerate(slots):
        total = 0
        for d in DCs:
            for k in SKUs:
                sku_info = wh_stock.get(k, {})
                sku_reefer = sku_info.get("reefer_required", False)
                is_reefer_lorry = slot["lorry_type"] == "reefer"

                if sku_reefer and not is_reefer_lorry:
                    solver.Add(x[(s_idx, d, k)] == 0)
                if not sku_reefer and is_reefer_lorry:
                    solver.Add(x[(s_idx, d, k)] == 0)

                total += x[(s_idx, d, k)]

        solver.Add(total <= slot["capacity_units"])

    # 4. Inventory constraint
    for k in SKUs:
        total_loaded = sum(x[(s_idx, d, k)] for s_idx in range(len(slots)) for d in DCs)
        avail = wh_stock.get(k, {}).get("effective", 0)
        solver.Add(total_loaded <= avail)

    # 5. Demand constraint
    demand_map = {}
    for req in requests:
        demand_map[(req["dc_id"], req["sku_id"])] = req["requested_quantity"]

    for (dc, sku), max_qty in demand_map.items():
        if sku in SKUs:
            total_to_dc = sum(x[(s_idx, dc, sku)] for s_idx in range(len(slots)))
            solver.Add(total_to_dc <= max_qty)

    # ── Objective ────────────────────────────────────────────────────
    urgency_map = {(r["dc_id"], r["sku_id"]): r.get("urgency_score", 50) for r in requests}

    objective = solver.Objective()

    if objective_mode == "urgency":
        # Maximize total dispatched × urgency
        for s_idx in range(len(slots)):
            for d in DCs:
                for k in SKUs:
                    urg = urgency_map.get((d, k), 0)
                    objective.SetCoefficient(x[(s_idx, d, k)], float(urg))
        objective.SetMaximization()

    elif objective_mode == "balanced":
        # Maximize coverage: reward visiting more unique DCs
        # Use urgency but add a penalty for not visiting a DC
        for s_idx in range(len(slots)):
            for d in DCs:
                for k in SKUs:
                    urg = urgency_map.get((d, k), 0)
                    objective.SetCoefficient(x[(s_idx, d, k)], float(urg))
                # Add bonus for visiting each DC
                objective.SetCoefficient(y[(s_idx, d)], 500.0)
        objective.SetMaximization()

    elif objective_mode == "cost":
        # Minimize cost while fulfilling as much as possible
        # Penalize travel cost, reward dispatched urgency
        for s_idx in range(len(slots)):
            for d in DCs:
                route = route_lookup.get(d, {"cost": 15000, "travel_time_hours": 6})
                cost_penalty = route["cost"] + route["travel_time_hours"] * 1000
                for k in SKUs:
                    urg = urgency_map.get((d, k), 0)
                    # Net coefficient: urgency reward - cost penalty per DC visit
                    objective.SetCoefficient(x[(s_idx, d, k)], float(urg))
                # Penalize visiting expensive DCs
                objective.SetCoefficient(y[(s_idx, d)], -cost_penalty)
        objective.SetMaximization()

    # Solve
    solver.SetTimeLimit(30000)  # 30s timeout
    status = solver.Solve()

    trace = {
        "solver": "SCIP",
        "objective_mode": objective_mode,
        "num_variables": solver.NumVariables(),
        "num_constraints": solver.NumConstraints(),
        "status": "optimal" if status == pywraplp.Solver.OPTIMAL else (
            "feasible" if status == pywraplp.Solver.FEASIBLE else "infeasible"
        ),
    }

    if status not in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
        logger.warning(f"M3 solver {objective_mode}: no feasible solution found")
        return _heuristic_solve(requests, wh_stock, slots, route_lookup, objective_mode)

    obj_val = objective.Value()
    trace["objective_value"] = obj_val

    # Extract solution into runs
    runs = _extract_runs(x, y, slots, DCs, SKUs, wh_stock, route_lookup)

    return runs, obj_val, trace


def _extract_runs(x, y, slots, DCs, SKUs, wh_stock, route_lookup) -> list[dict]:
    """Extract solver solution into the run/stop/item hierarchy."""
    runs = []

    for s_idx, slot in enumerate(slots):
        stops = []
        for d in DCs:
            if y[(s_idx, d)].solution_value() < 0.5:
                continue

            items = []
            for k in SKUs:
                qty = int(x[(s_idx, d, k)].solution_value())
                if qty > 0:
                    sku_info = wh_stock.get(k, {})
                    items.append({
                        "sku_id": k,
                        "sku_code": sku_info.get("sku_code", "UNKNOWN"),
                        "quantity": qty,
                        "dc_id": d,
                    })

            if items:
                route = route_lookup.get(d, {"travel_time_hours": 6.0, "cost": 15000})
                stops.append({
                    "dc_id": d,
                    "stop_sequence": len(stops) + 1,
                    "travel_time_hours": route["travel_time_hours"],
                    "items": items,
                })

        if stops:
            runs.append({
                "lorry_id": slot["lorry_id"],
                "registration": slot["registration"],
                "lorry_type": slot["lorry_type"],
                "capacity_units": slot["capacity_units"],
                "dispatch_day": slot["dispatch_day"],
                "stops": stops,
            })

    return runs


# ═══════════════════════════════════════════════════════════════════════
# HEURISTIC FALLBACK (used if OR-Tools isn't available or fails)
# ═══════════════════════════════════════════════════════════════════════


def _heuristic_solve(requests, wh_stock, slots, route_lookup, objective_mode):
    """Simple greedy heuristic fallback matching the stub behavior."""
    if objective_mode == "urgency":
        ordered_dcs = sorted(
            set(r["dc_id"] for r in requests),
            key=lambda dc: max((r.get("urgency_score", 50) for r in requests if r["dc_id"] == dc), default=0),
            reverse=True,
        )
    elif objective_mode == "cost":
        ordered_dcs = sorted(
            set(r["dc_id"] for r in requests),
            key=lambda dc: route_lookup.get(dc, {"cost": 999999})["cost"],
        )
    else:
        ordered_dcs = list(set(r["dc_id"] for r in requests))

    remaining_wh = {k: v["effective"] for k, v in wh_stock.items()}
    remaining_demand = {}
    for req in requests:
        key = (req["dc_id"], req["sku_id"])
        remaining_demand[key] = remaining_demand.get(key, 0) + req["requested_quantity"]

    runs = []
    total_utility = 0

    for slot in slots:
        stops = []
        remaining_cap = slot["capacity_units"]
        rr_idx = 0 if objective_mode == "balanced" else 0
        dc_order = ordered_dcs[rr_idx:] + ordered_dcs[:rr_idx] if objective_mode == "balanced" else ordered_dcs

        for dc in dc_order:
            if len(stops) >= MAX_STOPS_PER_LORRY or remaining_cap <= 0:
                break

            items = []
            loaded = 0
            for req in requests:
                if req["dc_id"] != dc:
                    continue
                key = (dc, req["sku_id"])
                rem = remaining_demand.get(key, 0)
                if rem <= 0:
                    continue

                sku_info = wh_stock.get(req["sku_id"], {})
                sku_reefer = sku_info.get("reefer_required", False)
                if sku_reefer and slot["lorry_type"] != "reefer":
                    continue
                if not sku_reefer and slot["lorry_type"] == "reefer":
                    continue

                avail = remaining_wh.get(req["sku_id"], 0)
                qty = min(rem, avail, remaining_cap - loaded)
                if qty <= 0:
                    continue

                items.append({
                    "sku_id": req["sku_id"],
                    "sku_code": sku_info.get("sku_code", "UNKNOWN"),
                    "quantity": qty,
                    "dc_id": dc,
                })
                remaining_demand[key] -= qty
                remaining_wh[req["sku_id"]] = max(0, avail - qty)
                loaded += qty
                total_utility += qty * req.get("urgency_score", 50)

            if items:
                route = route_lookup.get(dc, {"travel_time_hours": 6.0, "cost": 15000})
                remaining_cap -= loaded
                stops.append({
                    "dc_id": dc,
                    "stop_sequence": len(stops) + 1,
                    "travel_time_hours": route["travel_time_hours"],
                    "items": items,
                })

        if stops:
            runs.append({
                "lorry_id": slot["lorry_id"],
                "registration": slot["registration"],
                "lorry_type": slot["lorry_type"],
                "capacity_units": slot["capacity_units"],
                "dispatch_day": slot["dispatch_day"],
                "stops": stops,
            })

    trace = {
        "solver": "heuristic_fallback",
        "objective_mode": objective_mode,
        "status": "feasible",
        "objective_value": total_utility,
    }

    return runs, total_utility, trace


# ═══════════════════════════════════════════════════════════════════════
# PLAN PACKAGING — solver output → planner contract
# ═══════════════════════════════════════════════════════════════════════


def _package_plan(
    version_number: int,
    plan_name: str,
    generation_strategy: str,
    is_best: bool,
    runs: list[dict],
    objective_value: float,
    solver_trace: dict,
) -> dict:
    """Package solver output into the planner contract format."""
    flat_stops = []
    for run_data in runs:
        for stop in run_data["stops"]:
            flat_stops.append({
                "lorry_id": run_data["lorry_id"],
                "registration": run_data["registration"],
                "lorry_type": run_data["lorry_type"],
                "dispatch_day": run_data["dispatch_day"],
                **stop,
            })

    total_items_loaded = sum(
        item["quantity"]
        for run_data in runs
        for stop in run_data["stops"]
        for item in stop["items"]
    )

    score = round(objective_value / max(total_items_loaded, 1) if total_items_loaded > 0 else 0, 1)
    # Normalize score to reasonable range
    score = min(100, max(0, score))

    return {
        "version_number": version_number,
        "plan_name": plan_name,
        "score": score,
        "is_best": is_best,
        "runs": runs,
        "stops": flat_stops,
        "summary": {
            "total_runs": len(runs),
            "total_stops": len(flat_stops),
            "total_items_loaded": total_items_loaded,
        },
        # Traceability fields
        "generation_strategy": generation_strategy,
        "objective_value": objective_value,
        "solver_trace": solver_trace,
    }


# ═══════════════════════════════════════════════════════════════════════
# MAIN RUN FUNCTION — drop-in replacement for m3_stub.run()
# ═══════════════════════════════════════════════════════════════════════


def run(
    m2_requests: list[dict],
    warehouse_stock: dict,
    lorry_state: dict,
    route_graph: list[dict],
    sku_metadata: dict,
) -> list[dict]:
    """Run M3 real OR-Tools engine to generate 3 candidate dispatch plans.

    Returns list of plan dicts matching the planner contract.
    """
    logger.info("M3 Real Engine: Starting candidate plan generation")

    # Normalize inputs
    requests, wh_stock, lorries, route_lookup, slots = _normalize_inputs(
        m2_requests, warehouse_stock, lorry_state, route_graph, sku_metadata
    )

    if not requests or not slots:
        logger.warning("M3 Real Engine: No requests or lorry slots available")
        return []

    # ── Plan A: Urgency-maximizing ──────────────────────────────────
    logger.info("M3 solving Plan A (urgency-maximizing)")
    runs_a, obj_a, trace_a = _solve_dispatch(
        requests, wh_stock, slots, route_lookup, objective_mode="urgency"
    )

    plan_a = _package_plan(
        version_number=1,
        plan_name="Plan A — Urgency Priority",
        generation_strategy="urgency_max",
        is_best=True,
        runs=runs_a or [],
        objective_value=obj_a,
        solver_trace=trace_a,
    )

    # ── Plan B: Balanced coverage ───────────────────────────────────
    logger.info("M3 solving Plan B (balanced coverage)")
    runs_b, obj_b, trace_b = _solve_dispatch(
        requests, deepcopy(wh_stock), slots, route_lookup, objective_mode="balanced"
    )

    plan_b = _package_plan(
        version_number=2,
        plan_name="Plan B — Balanced Coverage",
        generation_strategy="balanced",
        is_best=False,
        runs=runs_b or [],
        objective_value=obj_b,
        solver_trace=trace_b,
    )

    # ── Plan C: Cost-aware ──────────────────────────────────────────
    logger.info("M3 solving Plan C (cost-aware)")
    runs_c, obj_c, trace_c = _solve_dispatch(
        requests, deepcopy(wh_stock), slots, route_lookup, objective_mode="cost"
    )

    plan_c = _package_plan(
        version_number=3,
        plan_name="Plan C — Cost Optimized",
        generation_strategy="cost_aware",
        is_best=False,
        runs=runs_c or [],
        objective_value=obj_c,
        solver_trace=trace_c,
    )

    logger.info(
        f"M3 Real Engine: Generated 3 plans — "
        f"A({len(runs_a or [])} runs), "
        f"B({len(runs_b or [])} runs), "
        f"C({len(runs_c or [])} runs)"
    )

    return [plan_a, plan_b, plan_c]
