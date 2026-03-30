"""Planner Flow Service — approve, reject, and override dispatch plans.

Handles the planner's decision workflow:
- Approve: freezes plan, creates demo_reservations + demo_transfers
- Reject: marks plan as rejected
- Override: validates changes via math-bound, creates new draft version
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session, joinedload

from apps.api.app.planner_flow.validation.math_bound import validate_override
from storage.models import (
    M3PlanVersion,
    M3PlanStop,
    M3PlanItem,
    PlannerDecision,
    OverrideReason,
    DemoReservation,
    DemoTransfer,
    AuditLog,
)


def approve_plan(
    session: Session,
    plan_version_id: int,
    approved_by: str = "planner",
) -> dict:
    """Approve a draft plan version.

    1. Validate plan is in draft status
    2. Freeze as approved with timestamp
    3. Create demo_reservations for all plan items (WH side)
    4. Create demo_transfers for all plan stops (DC side, status=in_transit)
    5. Log planner_decision + audit_log

    Returns:
        {success: bool, message: str, reservations_created: int, transfers_created: int}
    """
    plan = (
        session.query(M3PlanVersion)
        .options(
            joinedload(M3PlanVersion.stops).joinedload(M3PlanStop.items)
        )
        .filter(M3PlanVersion.id == plan_version_id)
        .first()
    )

    if not plan:
        return {"success": False, "message": f"Plan version {plan_version_id} not found."}

    if plan.plan_status != "draft":
        return {
            "success": False,
            "message": f"Plan version {plan_version_id} is '{plan.plan_status}', not 'draft'. "
                       f"Only draft plans can be approved.",
        }

    now = datetime.now(timezone.utc)

    # Mark plan as approved (immutable after this)
    plan.plan_status = "approved"
    plan.approved_at = now
    plan.approved_by = approved_by

    # Create demo_reservations and demo_transfers
    reservations_created = 0
    transfers_created = 0

    # Aggregate items by SKU for WH reservations
    sku_quantities: dict[int, int] = {}

    for stop in plan.stops:
        for item in stop.items:
            sku_quantities[item.sku_id] = sku_quantities.get(item.sku_id, 0) + item.quantity

            # Create transfer per stop-item (DC side)
            session.add(DemoTransfer(
                plan_version_id=plan.id,
                lorry_id=stop.lorry_id,
                dc_id=stop.dc_id,
                sku_id=item.sku_id,
                quantity=item.quantity,
                status="in_transit",
                dispatched_at=now,
            ))
            transfers_created += 1

    # Create WH reservations per SKU
    for sku_id, quantity in sku_quantities.items():
        session.add(DemoReservation(
            plan_version_id=plan.id,
            sku_id=sku_id,
            quantity_reserved=quantity,
            status="active",
        ))
        reservations_created += 1

    # Log planner decision
    session.add(PlannerDecision(
        plan_version_id=plan.id,
        decision_type="approve",
        decided_at=now,
        decided_by=approved_by,
        notes=f"Plan version {plan.version_number} approved.",
    ))

    # Audit log
    session.add(AuditLog(
        entity_type="plan_version",
        entity_id=plan.id,
        action="approved",
        actor=approved_by,
        timestamp=now,
        details={
            "version_number": plan.version_number,
            "reservations_created": reservations_created,
            "transfers_created": transfers_created,
        },
    ))

    session.commit()

    return {
        "success": True,
        "message": f"Plan version {plan.version_number} approved successfully.",
        "plan_version_id": plan.id,
        "reservations_created": reservations_created,
        "transfers_created": transfers_created,
    }


def reject_plan(
    session: Session,
    plan_version_id: int,
    notes: str = "",
    rejected_by: str = "planner",
) -> dict:
    """Reject a draft plan version.

    Returns:
        {success: bool, message: str}
    """
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

    session.add(PlannerDecision(
        plan_version_id=plan.id,
        decision_type="reject",
        decided_at=now,
        decided_by=rejected_by,
        notes=notes or "Plan rejected by planner.",
    ))

    session.add(AuditLog(
        entity_type="plan_version",
        entity_id=plan.id,
        action="rejected",
        actor=rejected_by,
        timestamp=now,
        details={"notes": notes},
    ))

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
    """Override a plan by creating a new draft version with specified changes.

    1. Validate the original plan exists and is draft
    2. Run math-bound validation on the proposed changes
    3. If valid, create a new draft version with changes applied
    4. Log override_reasons + decision + audit

    Args:
        changes: List of changes to apply:
            [{stop_index: int, items: [{sku_id, quantity}]}]
            or [{lorry_id, dc_id, items: [{sku_id, quantity}]}]

    Returns:
        {success: bool, message: str, validation: {...}, new_plan_version_id?: int}
    """
    original = (
        session.query(M3PlanVersion)
        .options(
            joinedload(M3PlanVersion.stops).joinedload(M3PlanStop.items)
        )
        .filter(M3PlanVersion.id == plan_version_id)
        .first()
    )

    if not original:
        return {"success": False, "message": f"Plan version {plan_version_id} not found."}

    if original.plan_status != "draft":
        return {
            "success": False,
            "message": f"Can only override draft plans. Current status: '{original.plan_status}'.",
        }

    # Build proposed stops from changes (merge with original)
    proposed_stops = _apply_changes(original, changes)

    # Validate with math-bound check
    validation = validate_override(session, proposed_stops)

    if not validation["valid"]:
        return {
            "success": False,
            "message": "Validation failed. Override rejected.",
            "validation": validation,
        }

    now = datetime.now(timezone.utc)

    # Find the next version number for this engine run
    max_version = (
        session.query(M3PlanVersion.version_number)
        .filter(M3PlanVersion.engine_run_id == original.engine_run_id)
        .order_by(M3PlanVersion.version_number.desc())
        .first()
    )
    new_version_number = (max_version[0] + 1) if max_version else 1

    # Create new draft plan version
    new_plan = M3PlanVersion(
        engine_run_id=original.engine_run_id,
        version_number=new_version_number,
        plan_status="draft",
        score=original.score,
        is_best=False,
    )
    session.add(new_plan)
    session.flush()

    # Create stops and items from the proposed structure
    for stop_data in proposed_stops:
        stop = M3PlanStop(
            plan_version_id=new_plan.id,
            lorry_id=stop_data["lorry_id"],
            stop_sequence=stop_data.get("stop_sequence", 1),
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

    # Log override decision
    decision = PlannerDecision(
        plan_version_id=new_plan.id,
        decision_type="override",
        decided_at=now,
        decided_by=override_by,
        notes=notes or f"Override of plan version {original.version_number}.",
    )
    session.add(decision)
    session.flush()

    # Log override reasons (changes applied)
    for i, change in enumerate(changes):
        session.add(OverrideReason(
            decision_id=decision.id,
            field_changed=f"stop_{i}",
            old_value=str(_summarize_stop(original, i)),
            new_value=str(change),
            reason=notes or "Planner manual override",
        ))

    # Audit log
    session.add(AuditLog(
        entity_type="plan_version",
        entity_id=new_plan.id,
        action="overridden",
        actor=override_by,
        timestamp=now,
        details={
            "original_plan_version_id": original.id,
            "original_version_number": original.version_number,
            "new_version_number": new_version_number,
            "changes_count": len(changes),
        },
    ))

    session.commit()

    return {
        "success": True,
        "message": f"Override successful. New draft version {new_version_number} created.",
        "new_plan_version_id": new_plan.id,
        "new_version_number": new_version_number,
        "validation": validation,
    }


def _apply_changes(original: M3PlanVersion, changes: list[dict]) -> list[dict]:
    """Merge override changes with the original plan structure.

    If changes contain complete stop definitions (lorry_id, dc_id, items),
    use those directly. Otherwise, overlay changes onto original stops.
    """
    # If changes look like complete stop definitions, use directly
    if changes and "lorry_id" in changes[0] and "dc_id" in changes[0]:
        return changes

    # Otherwise, copy original stops and apply modifications
    proposed_stops = []
    for stop in original.stops:
        stop_dict = {
            "lorry_id": stop.lorry_id,
            "dc_id": stop.dc_id,
            "stop_sequence": stop.stop_sequence,
            "items": [
                {"sku_id": item.sku_id, "quantity": item.quantity}
                for item in stop.items
            ],
        }
        proposed_stops.append(stop_dict)

    # Apply changes by stop_index
    for change in changes:
        idx = change.get("stop_index", -1)
        if 0 <= idx < len(proposed_stops):
            if "items" in change:
                proposed_stops[idx]["items"] = change["items"]
            if "lorry_id" in change:
                proposed_stops[idx]["lorry_id"] = change["lorry_id"]
            if "dc_id" in change:
                proposed_stops[idx]["dc_id"] = change["dc_id"]

    return proposed_stops


def _summarize_stop(plan: M3PlanVersion, index: int) -> dict:
    """Summarize original stop at given index for audit logging."""
    stops = list(plan.stops)
    if index < len(stops):
        stop = stops[index]
        return {
            "lorry_id": stop.lorry_id,
            "dc_id": stop.dc_id,
            "items": [{"sku_id": i.sku_id, "quantity": i.quantity} for i in stop.items],
        }
    return {"note": "stop index out of bounds"}
