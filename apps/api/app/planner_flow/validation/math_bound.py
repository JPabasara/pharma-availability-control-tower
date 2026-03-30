"""Math-Bound Validation for planner overrides.

Validates that manual plan adjustments respect physical constraints:
1. total_load ≤ lorry.capacity_units for each lorry
2. quantity ≤ effective_wh_stock for each SKU
3. Reefer lorry → only reefer SKUs
4. Normal lorry → only normal SKUs
"""

from sqlalchemy.orm import Session

from storage.models import Lorry, SKU
from integrations.inbound.warehouse_stock_reader import reader as wh_reader


def validate_override(
    session: Session,
    stops: list[dict],
) -> dict:
    """Validate a proposed plan override against physical constraints.

    Args:
        session: DB session
        stops: List of proposed stops:
            [{lorry_id, dc_id, items: [{sku_id, quantity}]}]

    Returns:
        {
            valid: bool,
            errors: [str],
            warnings: [str]
        }
    """
    errors = []
    warnings = []

    # Load current effective WH stock
    wh_contract = wh_reader.get_latest_contract(session)
    wh_stock: dict[int, int] = {}
    if wh_contract:
        for item in wh_contract["items"]:
            wh_stock[item["sku_id"]] = item["effective"]

    # Load lorry master data
    lorry_cache: dict[int, Lorry] = {}
    # Load SKU master data
    sku_cache: dict[int, SKU] = {}

    # Track total allocation per SKU across all stops
    total_sku_allocation: dict[int, int] = {}

    for stop in stops:
        lorry_id = stop["lorry_id"]

        # Fetch lorry
        if lorry_id not in lorry_cache:
            lorry = session.query(Lorry).filter(Lorry.id == lorry_id).first()
            if not lorry:
                errors.append(f"Lorry ID {lorry_id} not found.")
                continue
            lorry_cache[lorry_id] = lorry
        lorry = lorry_cache[lorry_id]

        # --- Check 1: Capacity constraint ---
        total_load = sum(item.get("quantity", 0) for item in stop.get("items", []))
        if total_load > lorry.capacity_units:
            errors.append(
                f"Lorry {lorry.registration} (ID {lorry_id}): "
                f"load {total_load} exceeds capacity {lorry.capacity_units}."
            )

        # Check each item
        for item in stop.get("items", []):
            sku_id = item["sku_id"]
            qty = item.get("quantity", 0)

            # Fetch SKU
            if sku_id not in sku_cache:
                sku = session.query(SKU).filter(SKU.id == sku_id).first()
                if not sku:
                    errors.append(f"SKU ID {sku_id} not found.")
                    continue
                sku_cache[sku_id] = sku
            sku = sku_cache[sku_id]

            # --- Check 3/4: Reefer segregation ---
            if lorry.lorry_type == "reefer" and not sku.reefer_required:
                errors.append(
                    f"Lorry {lorry.registration} is reefer but SKU {sku.code} "
                    f"does not require reefer."
                )
            if lorry.lorry_type == "normal" and sku.reefer_required:
                errors.append(
                    f"Lorry {lorry.registration} is normal but SKU {sku.code} "
                    f"requires reefer transport."
                )

            # Track total allocation
            total_sku_allocation[sku_id] = total_sku_allocation.get(sku_id, 0) + qty

    # --- Check 2: WH stock sufficiency ---
    for sku_id, total_qty in total_sku_allocation.items():
        available = wh_stock.get(sku_id, 0)
        if total_qty > available:
            sku = sku_cache.get(sku_id)
            sku_label = sku.code if sku else f"ID {sku_id}"
            errors.append(
                f"SKU {sku_label}: total allocation {total_qty} exceeds "
                f"effective WH stock {available}."
            )

    # Warnings for near-capacity
    for stop in stops:
        lorry_id = stop["lorry_id"]
        lorry = lorry_cache.get(lorry_id)
        if lorry:
            total_load = sum(item.get("quantity", 0) for item in stop.get("items", []))
            utilization = total_load / lorry.capacity_units if lorry.capacity_units > 0 else 0
            if 0.9 <= utilization < 1.0:
                warnings.append(
                    f"Lorry {lorry.registration}: {utilization:.0%} capacity utilized."
                )

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }
