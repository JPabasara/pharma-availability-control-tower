"""Math-Bound Validation for planner overrides."""

from apps.api.app.dependencies.business_time import get_planning_dates
from sqlalchemy.orm import Session

from integrations.inbound.warehouse_stock_reader import reader as wh_reader
from storage.models import DemoLorryDayState, Lorry, SKU


def validate_override(
    session: Session,
    runs: list[dict],
) -> dict:
    """Validate a proposed run-based override against physical constraints."""
    errors: list[str] = []
    warnings: list[str] = []

    wh_contract = wh_reader.get_latest_contract(session)
    wh_stock = {
        item["sku_id"]: item["effective"]
        for item in (wh_contract.get("items", []) if wh_contract else [])
    }
    planning_dates = get_planning_dates()

    lorry_cache: dict[int, Lorry] = {}
    sku_cache: dict[int, SKU] = {}
    total_sku_allocation: dict[int, int] = {}
    seen_lorry_days: set[tuple[int, int]] = set()

    blocked_rows = (
        session.query(DemoLorryDayState)
        .filter(DemoLorryDayState.business_date.in_(planning_dates))
        .all()
    )
    blocked_lookup = {
        (row.lorry_id, row.business_date.isoformat()): row
        for row in blocked_rows
    }

    for run in runs:
        lorry_id = run["lorry_id"]
        dispatch_day = int(run.get("dispatch_day", 0))
        stops = run.get("stops", [])

        if dispatch_day not in (1, 2):
            errors.append(f"Lorry {lorry_id}: dispatch_day must be 1 or 2.")
            continue
        if len(stops) > 2:
            errors.append(f"Lorry {lorry_id} Day {dispatch_day}: more than 2 stops are not allowed.")

        if lorry_id not in lorry_cache:
            lorry = session.query(Lorry).filter(Lorry.id == lorry_id).first()
            if not lorry:
                errors.append(f"Lorry ID {lorry_id} not found.")
                continue
            lorry_cache[lorry_id] = lorry
        lorry = lorry_cache[lorry_id]

        lorry_day_key = (lorry_id, dispatch_day)
        if lorry_day_key in seen_lorry_days:
            errors.append(
                f"Lorry {lorry.registration} is assigned more than once on Day {dispatch_day}."
            )
        seen_lorry_days.add(lorry_day_key)

        target_date = planning_dates[dispatch_day - 1].isoformat()
        blocked = blocked_lookup.get((lorry_id, target_date))
        if blocked and blocked.status in {"unavailable", "assigned"}:
            errors.append(
                f"Lorry {lorry.registration} is {blocked.status} on Day {dispatch_day}."
            )

        total_load = sum(
            item.get("quantity", 0)
            for stop in stops
            for item in stop.get("items", [])
        )
        if total_load > lorry.capacity_units:
            errors.append(
                f"Lorry {lorry.registration} on Day {dispatch_day}: "
                f"load {total_load} exceeds capacity {lorry.capacity_units}."
            )
        elif lorry.capacity_units > 0:
            utilization = total_load / lorry.capacity_units
            if 0.9 <= utilization < 1.0:
                warnings.append(
                    f"Lorry {lorry.registration} Day {dispatch_day}: {utilization:.0%} capacity utilized."
                )

        for stop in stops:
            for item in stop.get("items", []):
                sku_id = item["sku_id"]
                qty = item.get("quantity", 0)
                if sku_id not in sku_cache:
                    sku = session.query(SKU).filter(SKU.id == sku_id).first()
                    if not sku:
                        errors.append(f"SKU ID {sku_id} not found.")
                        continue
                    sku_cache[sku_id] = sku
                sku = sku_cache[sku_id]

                if lorry.lorry_type == "reefer" and not sku.reefer_required:
                    errors.append(
                        f"Lorry {lorry.registration} is reefer but SKU {sku.code} does not require reefer."
                    )
                if lorry.lorry_type == "normal" and sku.reefer_required:
                    errors.append(
                        f"Lorry {lorry.registration} is normal but SKU {sku.code} requires reefer transport."
                    )

                total_sku_allocation[sku_id] = total_sku_allocation.get(sku_id, 0) + qty

    for sku_id, total_qty in total_sku_allocation.items():
        available = wh_stock.get(sku_id, 0)
        if total_qty > available:
            sku = sku_cache.get(sku_id)
            sku_label = sku.code if sku else f"ID {sku_id}"
            errors.append(
                f"SKU {sku_label}: total allocation {total_qty} exceeds effective WH stock {available}."
            )

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }
