"""Orchestration service for singleton M1/M2/M3 planning flows."""

from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from apps.api.app.dependencies.business_time import get_planning_dates
from apps.api.app.orchestration import engine_bridge
from integrations.inbound.dc_stock_reader import reader as dc_reader
from integrations.inbound.eta_provider import provider as eta_provider
from integrations.inbound.lorry_state_reader import reader as lorry_reader
from integrations.inbound.manifest_reader import reader as manifest_reader
from integrations.inbound.sales_history_reader import reader as sales_reader
from integrations.inbound.warehouse_stock_reader import reader as wh_reader
from storage.models import (
    EngineRun,
    M1Result,
    M2Request,
    M3PlanItem,
    M3PlanRun,
    M3PlanStop,
    M3PlanVersion,
    RouteEdge,
    SKU,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def format_planning_date(value: date) -> str:
    """Format a business date with an explicit month/day/year."""
    return f"{value.strftime('%B')} {value.day}, {value.year}"


def get_current_planning_dates() -> list[date]:
    """Return the current two-day planning horizon."""
    return get_planning_dates()


def get_current_planning_start_date() -> date:
    """Return the business Day 1 for the current planning horizon."""
    return get_current_planning_dates()[0]


def get_latest_engine_run(session: Session, engine_type: str) -> EngineRun | None:
    """Fetch the newest engine run for an engine type."""
    return (
        session.query(EngineRun)
        .filter(EngineRun.engine_type == engine_type)
        .order_by(EngineRun.started_at.desc(), EngineRun.id.desc())
        .first()
    )


def get_generated_at_iso(run: EngineRun | None) -> str | None:
    """Return the canonical completed/started timestamp for UI display."""
    if not run:
        return None
    timestamp = run.completed_at or run.started_at
    return timestamp.isoformat() if timestamp else None


def get_latest_m2_requests(session: Session) -> tuple[list[dict], EngineRun | None]:
    """Return the latest singleton M2 request set and its run."""
    run = get_latest_engine_run(session, "m2")
    if not run:
        return [], None

    requests = (
        session.query(M2Request)
        .filter(M2Request.engine_run_id == run.id)
        .order_by(M2Request.id.asc())
        .all()
    )
    result = [
        {
            "dc_id": request.dc_id,
            "sku_id": request.sku_id,
            "requested_quantity": request.requested_quantity,
            "urgency": request.urgency,
            "required_by": request.required_by.isoformat() if request.required_by else None,
        }
        for request in requests
    ]
    return result, run


def get_current_m3_draft_run(session: Session) -> EngineRun | None:
    """Return the engine run that owns the current live M3 draft set."""
    return (
        session.query(EngineRun)
        .join(M3PlanVersion, M3PlanVersion.engine_run_id == EngineRun.id)
        .filter(
            EngineRun.engine_type == "m3",
            M3PlanVersion.plan_status == "draft",
        )
        .order_by(EngineRun.started_at.desc(), EngineRun.id.desc())
        .first()
    )


def get_current_m3_draft_plans(session: Session) -> tuple[list[M3PlanVersion], EngineRun | None]:
    """Return the live M3 draft candidate set."""
    run = get_current_m3_draft_run(session)
    if not run:
        return [], None

    plans = (
        session.query(M3PlanVersion)
        .filter(
            M3PlanVersion.engine_run_id == run.id,
            M3PlanVersion.plan_status == "draft",
        )
        .order_by(M3PlanVersion.version_number.asc(), M3PlanVersion.id.asc())
        .all()
    )
    return plans, run


def _get_route_graph(session: Session) -> list[dict]:
    """Load the route graph from master data."""
    edges = session.query(RouteEdge).all()
    return [
        {
            "id": edge.id,
            "origin_type": edge.origin_type,
            "origin_id": edge.origin_id,
            "destination_type": edge.destination_type,
            "destination_id": edge.destination_id,
            "travel_time_hours": edge.travel_time_hours,
            "cost": edge.cost,
        }
        for edge in edges
    ]


def _get_sku_metadata(session: Session) -> dict[int, dict]:
    """Load SKU master data as a lookup dictionary."""
    skus = session.query(SKU).all()
    return {
        sku.id: {
            "id": sku.id,
            "code": sku.code,
            "name": sku.name,
            "category": sku.category,
            "reefer_required": sku.reefer_required,
        }
        for sku in skus
    }


def _cleanup_orphan_m3_runs(session: Session) -> None:
    """Delete M3 engine runs that no longer own any plan versions."""
    all_run_ids = [
        row[0]
        for row in session.query(EngineRun.id)
        .filter(EngineRun.engine_type == "m3")
        .all()
    ]
    if not all_run_ids:
        return

    active_run_ids = {
        row[0]
        for row in session.query(M3PlanVersion.engine_run_id)
        .filter(M3PlanVersion.engine_run_id.in_(all_run_ids))
        .distinct()
        .all()
    }
    orphaned_ids = set(all_run_ids) - active_run_ids
    if orphaned_ids:
        (
            session.query(EngineRun)
            .filter(EngineRun.id.in_(orphaned_ids))
            .delete(synchronize_session=False)
        )


def purge_live_m3_drafts(session: Session) -> None:
    """Delete every live M3 draft so only the next generated set remains."""
    for plan in session.query(M3PlanVersion).filter(M3PlanVersion.plan_status == "draft").all():
        session.delete(plan)
    session.flush()
    _cleanup_orphan_m3_runs(session)


def get_m3_lock_state(session: Session) -> dict:
    """Return lock metadata for the current planning horizon."""
    planning_dates = get_current_planning_dates()
    planning_start_date = planning_dates[0]

    approved_version_ids = [
        row[0]
        for row in (
            session.query(M3PlanVersion.id)
            .join(EngineRun, M3PlanVersion.engine_run_id == EngineRun.id)
            .filter(
                M3PlanVersion.plan_status == "approved",
                EngineRun.engine_type == "m3",
                EngineRun.planning_start_date == planning_start_date,
            )
            .all()
        )
    ]

    locked = False
    if approved_version_ids:
        approved_days = {
            row[0]
            for row in (
                session.query(M3PlanRun.dispatch_day)
                .filter(M3PlanRun.plan_version_id.in_(approved_version_ids))
                .distinct()
                .all()
            )
        }
        locked = 1 in approved_days and 2 in approved_days

    lock_reason = None
    if locked:
        lock_reason = (
            "M3 is locked until the next business day because dispatch plans for "
            f"{format_planning_date(planning_dates[0])} and {format_planning_date(planning_dates[1])} "
            "are already approved."
        )

    return {
        "locked": locked,
        "lock_reason": lock_reason,
        "planning_start_date": planning_start_date.isoformat(),
    }


def check_m3_locked(session: Session) -> bool:
    """Backward-compatible bool helper for M3 locking."""
    return bool(get_m3_lock_state(session)["locked"])


def refresh_m2(session: Session) -> dict:
    """Run M2 independently and keep only the latest singleton result set."""
    now = _utc_now()
    planning_start_date = get_current_planning_start_date()

    session.query(M2Request).delete(synchronize_session=False)
    (
        session.query(EngineRun)
        .filter(EngineRun.engine_type == "m2")
        .delete(synchronize_session=False)
    )
    session.flush()

    dc_contracts = dc_reader.get_all_latest_contracts(session)
    sales_forecasts = sales_reader.to_contract(session)
    input_snapshot_ids = {
        "dc_stock_snapshot_ids": [dc["snapshot_id"] for dc in dc_contracts],
    }

    m2_mode = engine_bridge.get_engine_mode("m2")
    m2_run = EngineRun(
        engine_type="m2",
        started_at=now,
        completed_at=None,
        status="running",
        planning_start_date=planning_start_date,
        input_snapshot_ids=input_snapshot_ids,
        engine_mode=m2_mode,
        engine_impl="m2_xgboost_v1" if m2_mode == "real" else "stub",
    )
    session.add(m2_run)
    session.flush()

    m2_results = engine_bridge.run_m2(dc_contracts, sales_forecasts)
    for result in m2_results:
        request = M2Request(
            engine_run_id=m2_run.id,
            dc_id=result["dc_id"],
            sku_id=result["sku_id"],
            requested_quantity=result["requested_quantity"],
            urgency=result["urgency"],
            required_by=datetime.fromisoformat(result["required_by"]),
        )
        if "urgency_score" in result:
            request.urgency_score = result["urgency_score"]
        if "shortage_probability" in result:
            request.shortage_probability = result["shortage_probability"]
        if "hours_until_shortage" in result:
            request.hours_until_shortage = result["hours_until_shortage"]
        if "effective_stock_at_run" in result:
            request.effective_stock_at_run = result["effective_stock_at_run"]
        if "projected_48h_sales" in result:
            request.projected_48h_sales = result["projected_48h_sales"]
        if "safety_stock" in result:
            request.safety_stock = result["safety_stock"]
        if "raw_features" in result:
            request.raw_features = result["raw_features"]
        session.add(request)

    m2_run.completed_at = _utc_now()
    m2_run.status = "completed"
    session.commit()

    return {
        "orchestration_time": now.isoformat(),
        "planning_start_date": planning_start_date.isoformat(),
        "m2_run_id": m2_run.id,
        "m2_requests_count": len(m2_results),
        "m2_requests": m2_results,
    }


def refresh_m1(session: Session) -> dict:
    """Run M1 after refreshing M2, keeping only the latest singleton result set."""
    refresh_m2(session)
    m2_results, _ = get_latest_m2_requests(session)

    now = _utc_now()
    planning_start_date = get_current_planning_start_date()

    session.query(M1Result).delete(synchronize_session=False)
    (
        session.query(EngineRun)
        .filter(EngineRun.engine_type == "m1")
        .delete(synchronize_session=False)
    )
    session.flush()

    manifest_contracts = manifest_reader.get_all_active_contracts(session)
    wh_contract = wh_reader.get_latest_contract(session)
    eta_contract = eta_provider.to_contract(session)
    sku_metadata = _get_sku_metadata(session)
    input_snapshot_ids = {
        "warehouse_stock_snapshot_id": wh_contract["snapshot_id"] if wh_contract else None,
        "manifest_snapshot_ids": [manifest["manifest_snapshot_id"] for manifest in manifest_contracts],
    }

    manifest_lines: list[dict] = []
    for contract in manifest_contracts:
        manifest_lines.extend(contract["lines"])

    m1_mode = engine_bridge.get_engine_mode("m1")
    m1_run = EngineRun(
        engine_type="m1",
        started_at=now,
        completed_at=None,
        status="running",
        planning_start_date=planning_start_date,
        input_snapshot_ids=input_snapshot_ids,
        engine_mode=m1_mode,
        engine_impl="m1_math_v1" if m1_mode == "real" else "stub",
    )
    session.add(m1_run)
    session.flush()

    m1_results = engine_bridge.run_m1(
        manifest_lines,
        wh_contract or {"items": []},
        m2_results,
        sku_metadata,
        eta_contract,
    )
    for result in m1_results:
        entry = M1Result(
            engine_run_id=m1_run.id,
            manifest_line_id=result["manifest_line_id"],
            sku_id=result["sku_id"],
            priority_score=result["priority_score"],
            priority_band=result["priority_band"],
            reefer_required=result["reefer_required"],
        )
        if "score_breakdown" in result:
            entry.score_breakdown = result["score_breakdown"]
        if "raw_features" in result:
            entry.raw_features = result["raw_features"]
        session.add(entry)

    m1_run.completed_at = _utc_now()
    m1_run.status = "completed"
    session.commit()

    return {
        "orchestration_time": now.isoformat(),
        "planning_start_date": planning_start_date.isoformat(),
        "m1_run_id": m1_run.id,
        "m1_results_count": len(m1_results),
        "m1_results": m1_results,
    }


def generate_plan(session: Session) -> dict:
    """Run the full singleton live planning flow: M2 -> M1 -> M3."""
    lock_state = get_m3_lock_state(session)
    if lock_state["locked"]:
        raise ValueError(lock_state["lock_reason"])

    refresh_m1(session)
    m2_results, _ = get_latest_m2_requests(session)

    now = _utc_now()
    planning_start_date = get_current_planning_start_date()
    purge_live_m3_drafts(session)

    wh_contract = wh_reader.get_latest_contract(session)
    lorry_contract = lorry_reader.get_latest_contract(session)
    route_graph = _get_route_graph(session)
    sku_metadata = _get_sku_metadata(session)
    input_snapshot_ids = {
        "warehouse_stock_snapshot_id": wh_contract["snapshot_id"] if wh_contract else None,
        "lorry_state_snapshot_id": lorry_contract["snapshot_id"] if lorry_contract else None,
    }

    m3_mode = engine_bridge.get_engine_mode("m3")
    m3_run = EngineRun(
        engine_type="m3",
        started_at=now,
        completed_at=None,
        status="running",
        planning_start_date=planning_start_date,
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
                    session.add(
                        M3PlanItem(
                            plan_stop_id=stop.id,
                            sku_id=item_data["sku_id"],
                            quantity=item_data["quantity"],
                        )
                    )

    m3_run.completed_at = _utc_now()
    m3_run.status = "completed"
    session.commit()

    return {
        "orchestration_time": now.isoformat(),
        "planning_start_date": planning_start_date.isoformat(),
        "m3_run_id": m3_run.id,
        "m3_plans_count": len(m3_plans),
        "m3_plans": m3_plans,
        "input_snapshot_ids": input_snapshot_ids,
    }


def _legacy_stops_to_runs(stops: list[dict]) -> list[dict]:
    """Convert legacy flat stop payloads into run payloads grouped by lorry/day."""
    grouped: dict[tuple[int, int], dict] = {}
    for stop in stops:
        key = (stop["lorry_id"], int(stop.get("dispatch_day", 1)))
        group = grouped.setdefault(
            key,
            {
                "lorry_id": stop["lorry_id"],
                "registration": stop.get("registration", "UNKNOWN"),
                "lorry_type": stop.get("lorry_type", "unknown"),
                "dispatch_day": int(stop.get("dispatch_day", 1)),
                "stops": [],
            },
        )
        group["stops"].append(
            {
                "dc_id": stop["dc_id"],
                "stop_sequence": stop["stop_sequence"],
                "items": stop.get("items", []),
            }
        )
    return list(grouped.values())
