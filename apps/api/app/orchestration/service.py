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


def refresh_m2(session: Session) -> dict:
    """Run M2 independently. Cleans up any prior M2 runs (Singleton)."""
    now = datetime.now(timezone.utc)

    # ── Singleton cleanup ──────────────────────────────────────────────
    session.query(M2Request).delete(synchronize_session=False)
    session.query(EngineRun).filter(EngineRun.engine_type == "m2").delete(synchronize_session=False)
    session.flush()

    # ── Step 1: Read inputs ────────────────────────────────────────────
    dc_contracts = dc_reader.get_all_latest_contracts(session)
    sales_forecasts = sales_reader.to_contract(session)

    input_snapshot_ids = {
        "dc_stock_snapshot_ids": [dc["snapshot_id"] for dc in dc_contracts],
    }

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

    for req in m2_results:
        m2_req = M2Request(
            engine_run_id=m2_run.id,
            dc_id=req["dc_id"],
            sku_id=req["sku_id"],
            requested_quantity=req["requested_quantity"],
            urgency=req["urgency"],
            required_by=datetime.fromisoformat(req["required_by"]),
        )
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
    session.commit()

    return {
        "orchestration_time": now.isoformat(),
        "m2_run_id": m2_run.id,
        "m2_requests_count": len(m2_results),
        "m2_requests": m2_results,
    }


def refresh_m1(session: Session) -> dict:
    """Run M1 independently. Auto-runs M2 if missing. Cleans up prior M1 runs."""
    # Ensure M2 exists; auto-run if NOT
    m2_run_exists = session.query(EngineRun).filter(EngineRun.engine_type == "m2").first()
    if not m2_run_exists:
        refresh_m2(session)
    
    # Retrieve latest M2 results from DB
    m2_db_requests = session.query(M2Request).all()
    m2_results = [
        {
            "dc_id": r.dc_id,
            "sku_id": r.sku_id,
            "requested_quantity": r.requested_quantity,
            "urgency": r.urgency,
            "required_by": r.required_by.isoformat() if r.required_by else None,
        }
        for r in m2_db_requests
    ]

    now = datetime.now(timezone.utc)

    # ── Singleton cleanup ──────────────────────────────────────────────
    session.query(M1Result).delete(synchronize_session=False)
    session.query(EngineRun).filter(EngineRun.engine_type == "m1").delete(synchronize_session=False)
    session.flush()

    # ── Read inputs ────────────────────────────────────────────────────
    manifest_contracts = manifest_reader.get_all_active_contracts(session)
    wh_contract = wh_reader.get_latest_contract(session)
    eta_contract = eta_provider.to_contract(session)
    sku_metadata = _get_sku_metadata(session)

    input_snapshot_ids = {
        "warehouse_stock_snapshot_id": wh_contract["snapshot_id"] if wh_contract else None,
        "manifest_snapshot_ids": [m["manifest_snapshot_id"] for m in manifest_contracts],
    }

    all_manifest_lines = []
    for mc in manifest_contracts:
        all_manifest_lines.extend(mc["lines"])

    # ── Run M1 ─────────────────────────────────────────────────────────
    m1_mode = engine_bridge.get_engine_mode("m1")
    m1_run = EngineRun(
        engine_type="m1",
        started_at=now,
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

    for res in m1_results:
        m1_res = M1Result(
            engine_run_id=m1_run.id,
            manifest_line_id=res["manifest_line_id"],
            sku_id=res["sku_id"],
            priority_score=res["priority_score"],
            priority_band=res["priority_band"],
            reefer_required=res["reefer_required"],
        )
        if "score_breakdown" in res:
            m1_res.score_breakdown = res["score_breakdown"]
        if "raw_features" in res:
            m1_res.raw_features = res["raw_features"]
        session.add(m1_res)

    m1_run.completed_at = datetime.now(timezone.utc)
    m1_run.status = "completed"
    session.commit()

    return {
        "orchestration_time": now.isoformat(),
        "m1_run_id": m1_run.id,
        "m1_results_count": len(m1_results),
        "m1_results": m1_results,
    }

def check_m3_locked(session: Session) -> bool:
    """Returns True if there are approved plans for BOTH Day 1 and Day 2."""
    approved_versions = session.query(M3PlanVersion.id).filter(
        M3PlanVersion.plan_status == "approved"
    ).all()
    approved_v_ids = [v[0] for v in approved_versions]
    if not approved_v_ids:
        return False

    days_query = session.query(M3PlanRun.dispatch_day).filter(
        M3PlanRun.plan_version_id.in_(approved_v_ids)
    ).distinct().all()
    days_set = {d[0] for d in days_query}
    return (1 in days_set) and (2 in days_set)


def generate_plan(session: Session) -> dict:
    """Generate M3 dispatch plan. Verifies lock, auto-runs M2 if missing, and clears old drafts."""
    if check_m3_locked(session):
        raise ValueError("System is locked: Dispatch plans for both Day 1 and Day 2 are already approved.")

    now = datetime.now(timezone.utc)

    # Ensure M2 exists; auto-run if NOT
    m2_run_exists = session.query(EngineRun).filter(EngineRun.engine_type == "m2").first()
    if not m2_run_exists:
        refresh_m2(session)
    
    # Retrieve latest M2 results from DB
    m2_db_requests = session.query(M2Request).all()
    m2_results = [
        {
            "dc_id": r.dc_id,
            "sku_id": r.sku_id,
            "requested_quantity": r.requested_quantity,
            "urgency": r.urgency,
            "required_by": r.required_by.isoformat() if r.required_by else None,
        }
        for r in m2_db_requests
    ]

    # ── Singleton cleanup for drafts ────────────────────────────────────
    draft_versions = session.query(M3PlanVersion).filter(
        M3PlanVersion.plan_status == "draft"
    ).all()
    for draft in draft_versions:
        session.delete(draft)
    session.flush()

    # Also cleanup orphaned M3 EngineRuns (runs that have NO plan_versions left)
    # SQLAlchemy might not allow this in a single neat delete, let's query them.
    all_m3_runs = session.query(EngineRun.id).filter(EngineRun.engine_type == "m3").all()
    if all_m3_runs:
        run_ids = [r[0] for r in all_m3_runs]
        runs_with_versions = session.query(M3PlanVersion.engine_run_id).filter(
            M3PlanVersion.engine_run_id.in_(run_ids)
        ).distinct().all()
        active_run_ids = {r[0] for r in runs_with_versions}
        orphans = set(run_ids) - active_run_ids
        if orphans:
            session.query(EngineRun).filter(EngineRun.id.in_(orphans)).delete(synchronize_session=False)

    # ── Read inputs for M3 ─────────────────────────────────────────────
    wh_contract = wh_reader.get_latest_contract(session)
    lorry_contract = lorry_reader.get_latest_contract(session)
    route_graph = _get_route_graph(session)
    sku_metadata = _get_sku_metadata(session)

    input_snapshot_ids = {
        "warehouse_stock_snapshot_id": wh_contract["snapshot_id"] if wh_contract else None,
        "lorry_state_snapshot_id": lorry_contract["snapshot_id"] if lorry_contract else None,
    }

    # ── Run M3 ─────────────────────────────────────────────────────────
    m3_mode = engine_bridge.get_engine_mode("m3")
    m3_run = EngineRun(
        engine_type="m3",
        started_at=now,
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

    for plan in m3_plans:
        plan_version = M3PlanVersion(
            engine_run_id=m3_run.id,
            version_number=plan["version_number"],
            plan_status="draft",
            score=plan.get("score"),
            is_best=plan.get("is_best", False),
            plan_name=plan.get("plan_name"),
            generation_strategy=plan.get("generation_strategy"),
            objective_value=plan.get("objective_value"),
            solver_trace=plan.get("solver_trace"),
        )
        session.add(plan_version)
        session.flush()

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
        "m3_run_id": m3_run.id,
        "m3_plans_count": len(m3_plans),
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

