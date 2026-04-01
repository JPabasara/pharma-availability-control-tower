"""Planner Flow Service — approve, reject, and override dispatch plans."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session, joinedload

from apps.api.app.dependencies.business_time import get_planning_dates
from apps.api.app.planner_flow.validation.math_bound import validate_override
from storage.models import (
    AuditLog,
    DemoLorryDayState,
    DemoReservation,
    DemoTransfer,
    M3PlanItem,
    M3PlanRun,
    M3PlanStop,
    M3PlanVersion,
    OverrideReason,
    PlannerDecision,
)


def approve_plan(
    session: Session,
    plan_version_id: int,
    approved_by: str = "planner",
) -> dict:
    """Approve a draft plan version and create operational overlays."""
    plan = _load_plan(session, plan_version_id)
    if not plan:
        return {"success": False, "message": f"Plan version {plan_version_id} not found."}
    if plan.plan_status != "draft":
        return {
            "success": False,
            "message": f"Plan version {plan_version_id} is '{plan.plan_status}', not 'draft'. Only draft plans can be approved.",
        }

    proposed_runs = _plan_to_runs(plan)
    validation = validate_override(session, proposed_runs)
    if not validation["valid"]:
        return {
            "success": False,
            "message": "Plan approval blocked by current lorry-day or stock constraints.",
            "validation": validation,
        }

    now = datetime.now(timezone.utc)
    planning_dates = get_planning_dates()

    plan.plan_status = "approved"
    plan.approved_at = now
    plan.approved_by = approved_by

    reservations_created = 0
    transfers_created = 0
    assignments_created = 0

    for run in plan.runs:
        target_date = planning_dates[run.dispatch_day - 1]
        day_state = (
            session.query(DemoLorryDayState)
            .filter(
                DemoLorryDayState.lorry_id == run.lorry_id,
                DemoLorryDayState.business_date == target_date,
            )
            .first()
        )
        if day_state:
            day_state.status = "assigned"
            day_state.source = "plan_approval"
        else:
            session.add(
                DemoLorryDayState(
                    lorry_id=run.lorry_id,
                    business_date=target_date,
                    status="assigned",
                    source="plan_approval",
                )
            )
        assignments_created += 1

        for stop in run.stops:
            for item in stop.items:
                session.add(
                    DemoReservation(
                        plan_version_id=plan.id,
                        plan_stop_id=stop.id,
                        sku_id=item.sku_id,
                        quantity_reserved=item.quantity,
                        status="active",
                    )
                )
                reservations_created += 1

                session.add(
                    DemoTransfer(
                        plan_version_id=plan.id,
                        plan_stop_id=stop.id,
                        lorry_id=run.lorry_id,
                        dc_id=stop.dc_id,
                        sku_id=item.sku_id,
                        quantity=item.quantity,
                        status="in_transit",
                        dispatched_at=now,
                    )
                )
                transfers_created += 1

    session.add(
        PlannerDecision(
            plan_version_id=plan.id,
            decision_type="approve",
            decided_at=now,
            decided_by=approved_by,
            notes=f"Plan version {plan.version_number} approved.",
        )
    )
    session.add(
        AuditLog(
            entity_type="plan_version",
            entity_id=plan.id,
            action="approved",
            actor=approved_by,
            timestamp=now,
            details={
                "version_number": plan.version_number,
                "reservations_created": reservations_created,
                "transfers_created": transfers_created,
                "lorry_assignments_created": assignments_created,
            },
        )
    )
    session.commit()

    return {
        "success": True,
        "message": f"Plan version {plan.version_number} approved successfully.",
        "plan_version_id": plan.id,
        "reservations_created": reservations_created,
        "transfers_created": transfers_created,
        "lorry_assignments_created": assignments_created,
    }


def reject_plan(
    session: Session,
    plan_version_id: int,
    notes: str = "",
    rejected_by: str = "planner",
) -> dict:
    """Reject a draft plan version."""
    plan = session.query(M3PlanVersion).filter(M3PlanVersion.id == plan_version_id).first()
    if not plan:
        return {"success": False, "message": f"Plan version {plan_version_id} not found."}
    if plan.plan_status != "draft":
        return {
            "success": False,
            "message": f"Plan version {plan_version_id} is '{plan.plan_status}', not 'draft'.",
        }

    now = datetime.now(timezone.utc)
    plan.plan_status = "rejected"
    session.add(
        PlannerDecision(
            plan_version_id=plan.id,
            decision_type="reject",
            decided_at=now,
            decided_by=rejected_by,
            notes=notes or "Plan rejected by planner.",
        )
    )
    session.add(
        AuditLog(
            entity_type="plan_version",
            entity_id=plan.id,
            action="rejected",
            actor=rejected_by,
            timestamp=now,
            details={"notes": notes},
        )
    )
    session.commit()
    return {
        "success": True,
        "message": f"Plan version {plan.version_number} rejected.",
        "plan_version_id": plan.id,
    }


def override_plan(
    session: Session,
    plan_version_id: int,
    changes: list[dict],
    override_by: str = "planner",
    notes: str = "",
) -> dict:
    """Override a plan by creating a new draft version."""
    original = _load_plan(session, plan_version_id)
    if not original:
        return {"success": False, "message": f"Plan version {plan_version_id} not found."}
    if original.plan_status != "draft":
        return {
            "success": False,
            "message": f"Can only override draft plans. Current status: '{original.plan_status}'.",
        }

    proposed_runs = _apply_changes(original, changes)
    validation = validate_override(session, proposed_runs)
    if not validation["valid"]:
        return {
            "success": False,
            "message": "Validation failed. Override rejected.",
            "validation": validation,
        }

    now = datetime.now(timezone.utc)
    max_version = (
        session.query(M3PlanVersion.version_number)
        .filter(M3PlanVersion.engine_run_id == original.engine_run_id)
        .order_by(M3PlanVersion.version_number.desc())
        .first()
    )
    new_version_number = (max_version[0] + 1) if max_version else 1

    new_plan = M3PlanVersion(
        engine_run_id=original.engine_run_id,
        version_number=new_version_number,
        plan_status="draft",
        score=original.score,
        is_best=False,
    )
    session.add(new_plan)
    session.flush()

    _persist_runs(session, new_plan.id, proposed_runs)

    decision = PlannerDecision(
        plan_version_id=new_plan.id,
        decision_type="override",
        decided_at=now,
        decided_by=override_by,
        notes=notes or f"Override of plan version {original.version_number}.",
    )
    session.add(decision)
    session.flush()

    for index, change in enumerate(proposed_runs):
        session.add(
            OverrideReason(
                decision_id=decision.id,
                field_changed=f"run_{index}",
                old_value=str(_summarize_run(original, index)),
                new_value=str(change),
                reason=notes or "Planner manual override",
            )
        )

    session.add(
        AuditLog(
            entity_type="plan_version",
            entity_id=new_plan.id,
            action="overridden",
            actor=override_by,
            timestamp=now,
            details={
                "original_plan_version_id": original.id,
                "original_version_number": original.version_number,
                "new_version_number": new_version_number,
                "changes_count": len(proposed_runs),
            },
        )
    )
    session.commit()

    return {
        "success": True,
        "message": f"Override successful. New draft version {new_version_number} created.",
        "new_plan_version_id": new_plan.id,
        "new_version_number": new_version_number,
        "validation": validation,
    }


def _load_plan(session: Session, plan_version_id: int) -> M3PlanVersion | None:
    return (
        session.query(M3PlanVersion)
        .options(
            joinedload(M3PlanVersion.runs)
            .joinedload(M3PlanRun.stops)
            .joinedload(M3PlanStop.items)
        )
        .filter(M3PlanVersion.id == plan_version_id)
        .first()
    )


def _persist_runs(session: Session, plan_version_id: int, runs: list[dict]) -> None:
    for run_data in runs:
        run = M3PlanRun(
            plan_version_id=plan_version_id,
            lorry_id=run_data["lorry_id"],
            dispatch_day=run_data.get("dispatch_day", 1),
        )
        session.add(run)
        session.flush()

        for stop_data in sorted(run_data.get("stops", []), key=lambda current: current.get("stop_sequence", 1)):
            stop = M3PlanStop(
                plan_run_id=run.id,
                stop_sequence=stop_data.get("stop_sequence", 1),
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


def _apply_changes(original: M3PlanVersion, changes: list[dict]) -> list[dict]:
    """Normalize incoming override payloads into full run definitions."""
    if changes and "dispatch_day" in changes[0] and "stops" in changes[0]:
        return _normalize_runs(changes)
    if changes and "lorry_id" in changes[0] and "dc_id" in changes[0]:
        return _legacy_stops_to_runs(changes)
    return _plan_to_runs(original)


def _normalize_runs(runs: list[dict]) -> list[dict]:
    normalized = []
    for run in runs:
        normalized.append({
            "lorry_id": run["lorry_id"],
            "dispatch_day": int(run.get("dispatch_day", 1)),
            "stops": [
                {
                    "dc_id": stop["dc_id"],
                    "stop_sequence": int(stop.get("stop_sequence", index + 1)),
                    "items": [
                        {"sku_id": item["sku_id"], "quantity": int(item["quantity"])}
                        for item in stop.get("items", [])
                        if int(item.get("quantity", 0)) > 0
                    ],
                }
                for index, stop in enumerate(run.get("stops", []))
            ],
        })
    return normalized


def _legacy_stops_to_runs(stops: list[dict]) -> list[dict]:
    grouped: dict[tuple[int, int], dict] = {}
    for stop in stops:
        key = (stop["lorry_id"], int(stop.get("dispatch_day", 1)))
        group = grouped.setdefault(
            key,
            {
                "lorry_id": stop["lorry_id"],
                "dispatch_day": int(stop.get("dispatch_day", 1)),
                "stops": [],
            },
        )
        group["stops"].append({
            "dc_id": stop["dc_id"],
            "stop_sequence": int(stop.get("stop_sequence", len(group["stops"]) + 1)),
            "items": stop.get("items", []),
        })
    return _normalize_runs(list(grouped.values()))


def _plan_to_runs(plan: M3PlanVersion) -> list[dict]:
    return _normalize_runs([
        {
            "lorry_id": run.lorry_id,
            "dispatch_day": run.dispatch_day,
            "stops": [
                {
                    "dc_id": stop.dc_id,
                    "stop_sequence": stop.stop_sequence,
                    "items": [
                        {"sku_id": item.sku_id, "quantity": item.quantity}
                        for item in stop.items
                    ],
                }
                for stop in sorted(run.stops, key=lambda current: (current.stop_sequence, current.id or 0))
            ],
        }
        for run in sorted(plan.runs, key=lambda current: (current.dispatch_day, current.id or 0))
    ])


def _summarize_run(plan: M3PlanVersion, index: int) -> dict:
    runs = _plan_to_runs(plan)
    if index < len(runs):
        return runs[index]
    return {"note": "run index out of bounds"}
