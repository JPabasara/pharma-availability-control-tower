"""M1 Stub — Manifest Intake Prioritization.

Deterministic heuristic scoring of manifest lines based on:
- Warehouse stock levels (lower stock → higher priority)
- Reefer requirement (+30 score bonus for cold-chain SKUs)
- ETA proximity (closer arrival → higher urgency)
- M2 requests (boost if DCs are requesting this SKU)
"""

from datetime import datetime, timezone


def run(
    manifest_lines: list[dict],
    warehouse_stock: dict,
    m2_requests: list[dict],
    sku_metadata: dict[int, dict],
    etas: list[dict],
) -> list[dict]:
    """Run M1 stub prioritization on manifest lines.

    Args:
        manifest_lines: List of {manifest_line_id, sku_id, sku_code, quantity, reefer_required}
        warehouse_stock: {items: [{sku_id, physical, reserved, effective}]}
        m2_requests: List of {dc_id, sku_id, requested_quantity, urgency}
        sku_metadata: Dict mapping sku_id → {code, name, reefer_required, ...}
        etas: List of {vessel_id, hours_until_arrival, ...}

    Returns:
        List of {manifest_line_id, sku_id, sku_code, priority_score, priority_band, reefer_required}
    """
    # Build stock lookup: sku_id → effective quantity
    stock_lookup: dict[int, int] = {}
    if warehouse_stock and "items" in warehouse_stock:
        for item in warehouse_stock["items"]:
            stock_lookup[item["sku_id"]] = item.get("effective", item.get("physical", 0))

    # Build M2 demand lookup: sku_id → total requested
    m2_demand: dict[int, int] = {}
    m2_urgency: dict[int, str] = {}
    for req in m2_requests:
        sid = req["sku_id"]
        m2_demand[sid] = m2_demand.get(sid, 0) + req["requested_quantity"]
        # Keep highest urgency
        urgency_rank = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        current = m2_urgency.get(sid, "low")
        if urgency_rank.get(req["urgency"], 0) > urgency_rank.get(current, 0):
            m2_urgency[sid] = req["urgency"]

    # Get min hours until arrival for ETA urgency scoring
    min_hours = 48.0
    for eta in etas:
        h = eta.get("hours_until_arrival", 48)
        if h < min_hours:
            min_hours = h

    results = []
    for line in manifest_lines:
        score = 50.0  # Base score
        sku_id = line["sku_id"]
        reefer = line.get("reefer_required", False)

        # --- Factor 1: Warehouse stock level ---
        wh_stock = stock_lookup.get(sku_id, 0)
        if wh_stock < 500:
            score += 40  # Critical stock
        elif wh_stock < 1000:
            score += 30  # Low stock
        elif wh_stock < 3000:
            score += 15  # Medium stock
        else:
            score += 5   # Adequate stock

        # --- Factor 2: Reefer bonus ---
        if reefer:
            score += 30  # Cold-chain SKUs get priority

        # --- Factor 3: ETA proximity ---
        if min_hours < 8:
            score += 20  # Imminent arrival
        elif min_hours < 16:
            score += 12
        elif min_hours < 24:
            score += 6

        # --- Factor 4: M2 demand pressure ---
        if sku_id in m2_demand:
            demand = m2_demand[sku_id]
            if m2_urgency.get(sku_id) == "critical":
                score += 25
            elif m2_urgency.get(sku_id) == "high":
                score += 15
            elif demand > 0:
                score += 8

        # Clamp score to 0-100
        score = max(0, min(100, score))

        # Determine priority band
        if score >= 80:
            band = "critical"
        elif score >= 60:
            band = "high"
        elif score >= 40:
            band = "medium"
        else:
            band = "low"

        results.append({
            "manifest_line_id": line["manifest_line_id"],
            "sku_id": sku_id,
            "sku_code": line.get("sku_code", "UNKNOWN"),
            "priority_score": round(score, 1),
            "priority_band": band,
            "reefer_required": reefer,
        })

    # Sort by priority score descending
    results.sort(key=lambda x: x["priority_score"], reverse=True)
    return results
