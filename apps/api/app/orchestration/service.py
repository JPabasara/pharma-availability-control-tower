"""Orchestration Service — the main pipeline that assembles inputs and runs M2→M1→M3.

Triggered by the planner clicking "Generate Plan". This service:
1. Reads all snapshot data via readers
2. Runs M2 (needs forecasts + DC stock)
3. Runs M1 (needs manifests + WH stock + M2 results + ETAs) — planner-facing only
4. Runs M3 (needs M2 + WH stock + lorries + routes + SKU metadata) — does NOT use M1
5. Persists all engine_run records and results
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from apps.api.app.orchestration import engine_bridge
from integrations.inbound.manifest_reader import reader as manifest_reader
from integrations.inbound.warehouse_stock_reader import reader as wh_reader
from integrations.inbound.dc_stock_reader import reader as dc_reader
from integrations.inbound.sales_history_reader import reader as sales_reader
from integrations.inbound.lorry_state_reader import reader as lorry_reader
from integrations.inbound.eta_provider import provider as eta_provider
from storage.models import (
    EngineRun,
    M1Result,
    M2Request,
    M3PlanVersion,
    M3PlanRun,
    M3PlanStop,
    M3PlanItem,
    RouteEdge,
    SKU,
)


def _get_route_graph(session: Session) -> list[dict]:
    """Load the route graph from master data."""
    edges = session.query(RouteEdge).all()
    return [
        {
            "id": e.id,
            "origin_type": e.origin_type,
            "origin_id": e.origin_id,
            "destination_type": e.destination_type,
            "destination_id": e.destination_id,
            "travel_time_hours": e.travel_time_hours,
            "cost": e.cost,
        }
        for e in edges
    ]


def _get_sku_metadata(session: Session) -> dict[int, dict]:
    """Load SKU master data as a lookup dict."""
    skus = session.query(SKU).all()
    return {
        s.id: {
            "id": s.id,
            "code": s.code,
            "name": s.name,
            "category": s.category,
            "reefer_required": s.reefer_required,
        }
        for s in skus
    }


def generate_plan(session: Session) -> dict:
    """Execute the full orchestration pipeline: Read → M2 → M1 → M3 → Persist.

    Returns:
        {
            orchestration_id: str,
            m2_run_id: int,
            m1_run_id: int,
            m3_run_id: int,
            m2_requests: [...],
            m1_results: [...],
            m3_plans: [...],
            input_snapshot_ids: {...}
        }
    """
    now = datetime.now(timezone.utc)

    # ── Step 1: Read all inputs ─────────────────────────────────────────
    manifest_contracts = manifest_reader.get_all_active_contracts(session)
    wh_contract = wh_reader.get_latest_contract(session)
    dc_contracts = dc_reader.get_all_latest_contracts(session)
    sales_forecasts = sales_reader.to_contract(session)
    lorry_contract = lorry_reader.get_latest_contract(session)
    eta_contract = eta_provider.to_contract(session)
    route_graph = _get_route_graph(session)
    sku_metadata = _get_sku_metadata(session)

    # Collect snapshot IDs for traceability
    input_snapshot_ids = {
        "warehouse_stock_snapshot_id": wh_contract["snapshot_id"] if wh_contract else None,
        "dc_stock_snapshot_ids": [dc["snapshot_id"] for dc in dc_contracts],
        "lorry_state_snapshot_id": lorry_contract["snapshot_id"] if lorry_contract else None,
        "manifest_snapshot_ids": [m["manifest_snapshot_id"] for m in manifest_contracts],
    }

    # Flatten all manifest lines for M1
    all_manifest_lines = []
    for mc in manifest_contracts:
        all_manifest_lines.extend(mc["lines"])

    # ── Step 2: Run M2 ─────────────────────────────────────────────────
    m2_mode = engine_bridge.get_engine_mode("m2")
    m2_run = EngineRun(
        engine_type="m2",
        started_at=now,
        status="running",
        input_snapshot_ids=input_snapshot_ids,
        engine_mode=m2_mode,
        engine_impl="m2_xgboost_v1" if m2_mode == "real" else "stub",
    )
    session.add(m2_run)
    session.flush()

    m2_results = engine_bridge.run_m2(dc_contracts, sales_forecasts)

    # Persist M2 results
    for req in m2_results:
        m2_req = M2Request(
            engine_run_id=m2_run.id,
            dc_id=req["dc_id"],
            sku_id=req["sku_id"],
            requested_quantity=req["requested_quantity"],
            urgency=req["urgency"],
            required_by=datetime.fromisoformat(req["required_by"]),
        )
        # Persist trace fields if present (from real engine)
        if "urgency_score" in req:
            m2_req.urgency_score = req["urgency_score"]
        if "shortage_probability" in req:
            m2_req.shortage_probability = req["shortage_probability"]
        if "hours_until_shortage" in req:
            m2_req.hours_until_shortage = req["hours_until_shortage"]
        if "effective_stock_at_run" in req:
            m2_req.effective_stock_at_run = req["effective_stock_at_run"]
        if "projected_48h_sales" in req:
            m2_req.projected_48h_sales = req["projected_48h_sales"]
        if "safety_stock" in req:
            m2_req.safety_stock = req["safety_stock"]
        if "raw_features" in req:
            m2_req.raw_features = req["raw_features"]
        session.add(m2_req)

    m2_run.completed_at = datetime.now(timezone.utc)
    m2_run.status = "completed"
    session.flush()

    # ── Step 3: Run M1 (planner-facing only, not used by M3) ──────────
    m1_mode = engine_bridge.get_engine_mode("m1")
    m1_run = EngineRun(
        engine_type="m1",
        started_at=datetime.now(timezone.utc),
        status="running",
        input_snapshot_ids=input_snapshot_ids,
        engine_mode=m1_mode,
        engine_impl="m1_math_v1" if m1_mode == "real" else "stub",
    )
    session.add(m1_run)
    session.flush()

    m1_results = engine_bridge.run_m1(
        all_manifest_lines,
        wh_contract or {"items": []},
        m2_results,
        sku_metadata,
        eta_contract,
    )

    # Persist M1 results
    for res in m1_results:
        m1_res = M1Result(
            engine_run_id=m1_run.id,
            manifest_line_id=res["manifest_line_id"],
            sku_id=res["sku_id"],
            priority_score=res["priority_score"],
            priority_band=res["priority_band"],
            reefer_required=res["reefer_required"],
        )
        # Persist trace fields if present (from real engine)
        if "score_breakdown" in res:
            m1_res.score_breakdown = res["score_breakdown"]
        if "raw_features" in res:
            m1_res.raw_features = res["raw_features"]
        session.add(m1_res)

    m1_run.completed_at = datetime.now(timezone.utc)
    m1_run.status = "completed"
    session.flush()

    # ── Step 4: Run M3 (does NOT use M1 results) ──────────────────────
    m3_mode = engine_bridge.get_engine_mode("m3")
    m3_run = EngineRun(
        engine_type="m3",
        started_at=datetime.now(timezone.utc),
        status="running",
        input_snapshot_ids=input_snapshot_ids,
        engine_mode=m3_mode,
        engine_impl="m3_ortools_v1" if m3_mode == "real" else "stub",
    )
    session.add(m3_run)
    session.flush()

    m3_plans = engine_bridge.run_m3(
        m2_results,
        wh_contract or {"items": []},
        lorry_contract or {"lorries": []},
        route_graph,
        sku_metadata,
    )

    # Persist M3 plan versions
    for plan in m3_plans:
        plan_version = M3PlanVersion(
            engine_run_id=m3_run.id,
            version_number=plan["version_number"],
            plan_status="draft",
            score=plan.get("score"),
            is_best=plan.get("is_best", False),
            # Traceability fields (from real engine)
            plan_name=plan.get("plan_name"),
            generation_strategy=plan.get("generation_strategy"),
            objective_value=plan.get("objective_value"),
            solver_trace=plan.get("solver_trace"),
        )
        session.add(plan_version)
        session.flush()

        # Store plan_version_id back for the response
        plan["plan_version_id"] = plan_version.id

        runs = plan.get("runs") or _legacy_stops_to_runs(plan.get("stops", []))
        for run_data in runs:
            plan_run = M3PlanRun(
                plan_version_id=plan_version.id,
                lorry_id=run_data["lorry_id"],
                dispatch_day=run_data.get("dispatch_day", 1),
            )
            session.add(plan_run)
            session.flush()

            for stop_data in run_data.get("stops", []):
                stop = M3PlanStop(
                    plan_run_id=plan_run.id,
                    stop_sequence=stop_data["stop_sequence"],
                    dc_id=stop_data["dc_id"],
                )
                session.add(stop)
                session.flush()

                for item_data in stop_data.get("items", []):
                    session.add(M3PlanItem(
                        plan_stop_id=stop.id,
                        sku_id=item_data["sku_id"],
                        quantity=item_data["quantity"],
                    ))

    m3_run.completed_at = datetime.now(timezone.utc)
    m3_run.status = "completed"
    session.commit()

    return {
        "orchestration_time": now.isoformat(),
        "m2_run_id": m2_run.id,
        "m1_run_id": m1_run.id,
        "m3_run_id": m3_run.id,
        "m2_requests_count": len(m2_results),
        "m1_results_count": len(m1_results),
        "m3_plans_count": len(m3_plans),
        "m2_requests": m2_results,
        "m1_results": m1_results,
        "m3_plans": m3_plans,
        "input_snapshot_ids": input_snapshot_ids,
    }


def _legacy_stops_to_runs(stops: list[dict]) -> list[dict]:
    """Convert legacy flat stop payloads into day-1 runs grouped by lorry."""
    grouped: dict[int, dict] = {}
    for stop in stops:
        group = grouped.setdefault(
            stop["lorry_id"],
            {
                "lorry_id": stop["lorry_id"],
                "registration": stop.get("registration", "UNKNOWN"),
                "lorry_type": stop.get("lorry_type", "unknown"),
                "dispatch_day": stop.get("dispatch_day", 1),
                "stops": [],
            },
        )
        group["stops"].append({
            "dc_id": stop["dc_id"],
            "stop_sequence": stop["stop_sequence"],
            "items": stop.get("items", []),
        })
    return list(grouped.values())
