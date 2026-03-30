"""Orchestration Service — the main pipeline that assembles inputs and runs M1→M2→M3.

Triggered by the planner clicking "Generate Plan". This service:
1. Reads all snapshot data via readers
2. Runs M2 (needs forecasts + DC stock)
3. Runs M1 (needs manifests + WH stock + M2 results + ETAs)
4. Runs M3 (needs M1 + M2 + WH stock + lorries + routes)
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
    m2_run = EngineRun(
        engine_type="m2",
        started_at=now,
        status="running",
        input_snapshot_ids=input_snapshot_ids,
    )
    session.add(m2_run)
    session.flush()

    m2_results = engine_bridge.run_m2(dc_contracts, sales_forecasts)

    # Persist M2 results
    for req in m2_results:
        session.add(M2Request(
            engine_run_id=m2_run.id,
            dc_id=req["dc_id"],
            sku_id=req["sku_id"],
            requested_quantity=req["requested_quantity"],
            urgency=req["urgency"],
            required_by=datetime.fromisoformat(req["required_by"]),
        ))

    m2_run.completed_at = datetime.now(timezone.utc)
    m2_run.status = "completed"
    session.flush()

    # ── Step 3: Run M1 ─────────────────────────────────────────────────
    m1_run = EngineRun(
        engine_type="m1",
        started_at=datetime.now(timezone.utc),
        status="running",
        input_snapshot_ids=input_snapshot_ids,
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
        session.add(M1Result(
            engine_run_id=m1_run.id,
            manifest_line_id=res["manifest_line_id"],
            sku_id=res["sku_id"],
            priority_score=res["priority_score"],
            priority_band=res["priority_band"],
            reefer_required=res["reefer_required"],
        ))

    m1_run.completed_at = datetime.now(timezone.utc)
    m1_run.status = "completed"
    session.flush()

    # ── Step 4: Run M3 ─────────────────────────────────────────────────
    m3_run = EngineRun(
        engine_type="m3",
        started_at=datetime.now(timezone.utc),
        status="running",
        input_snapshot_ids=input_snapshot_ids,
    )
    session.add(m3_run)
    session.flush()

    m3_plans = engine_bridge.run_m3(
        m1_results,
        m2_results,
        wh_contract or {"items": []},
        lorry_contract or {"lorries": []},
        route_graph,
    )

    # Persist M3 plan versions
    for plan in m3_plans:
        plan_version = M3PlanVersion(
            engine_run_id=m3_run.id,
            version_number=plan["version_number"],
            plan_status="draft",
            score=plan.get("score"),
            is_best=plan.get("is_best", False),
        )
        session.add(plan_version)
        session.flush()

        # Store plan_version_id back for the response
        plan["plan_version_id"] = plan_version.id

        for stop_data in plan.get("stops", []):
            stop = M3PlanStop(
                plan_version_id=plan_version.id,
                lorry_id=stop_data["lorry_id"],
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
