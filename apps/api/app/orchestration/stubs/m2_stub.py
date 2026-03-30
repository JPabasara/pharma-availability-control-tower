"""M2 Stub — DC Replenishment Request Generator.

Compares effective DC stock against 48-hour sales forecast.
If forecast_48h > effective_dc_stock, generates a replenishment request.
Urgency is based on how many hours of demand the current stock covers.
"""

from datetime import datetime, timedelta, timezone


def run(
    dc_stock_contracts: list[dict],
    sales_forecasts: list[dict],
) -> list[dict]:
    """Run M2 stub to generate DC replenishment requests.

    Args:
        dc_stock_contracts: List of DC stock contracts from dc_stock_reader:
            [{dc_id, dc_code, items: [{sku_id, sku_code, effective, ...}]}]
        sales_forecasts: List of 48h forecasts from sales_history_reader:
            [{dc_id, sku_id, forecast_48h, daily_avg, ...}]

    Returns:
        List of {dc_id, dc_code, sku_id, sku_code, requested_quantity, urgency, required_by,
                 current_stock, forecast_48h, hours_coverage}
    """
    now = datetime.now(timezone.utc)

    # Build DC stock lookup: (dc_id, sku_id) → effective quantity
    stock_lookup: dict[tuple[int, int], dict] = {}
    for dc_contract in dc_stock_contracts:
        dc_id = dc_contract["dc_id"]
        for item in dc_contract.get("items", []):
            stock_lookup[(dc_id, item["sku_id"])] = {
                "effective": item["effective"],
                "sku_code": item.get("sku_code", "UNKNOWN"),
            }

    # Build forecast lookup: (dc_id, sku_id) → forecast info
    forecast_lookup: dict[tuple[int, int], dict] = {}
    for fc in sales_forecasts:
        forecast_lookup[(fc["dc_id"], fc["sku_id"])] = fc

    requests = []

    for (dc_id, sku_id), fc in forecast_lookup.items():
        forecast_48h = fc["forecast_48h"]
        daily_avg = fc["daily_avg"]

        stock_info = stock_lookup.get((dc_id, sku_id))
        effective_stock = stock_info["effective"] if stock_info else 0
        sku_code = stock_info["sku_code"] if stock_info else fc.get("sku_code", "UNKNOWN")

        # Only generate request if forecast exceeds current stock
        if forecast_48h <= 0 or effective_stock >= forecast_48h:
            continue

        # Calculate hours of coverage
        if daily_avg > 0:
            hourly_rate = daily_avg / 24
            hours_coverage = effective_stock / hourly_rate if hourly_rate > 0 else 999
        else:
            hours_coverage = 999  # No sales → no urgency

        # Determine urgency based on hours of stock coverage
        if hours_coverage < 12:
            urgency = "critical"
        elif hours_coverage < 24:
            urgency = "high"
        elif hours_coverage < 36:
            urgency = "medium"
        else:
            urgency = "low"

        # Requested quantity: fill the gap + 20% buffer
        gap = forecast_48h - effective_stock
        requested_qty = int(gap * 1.2)

        # Required by: based on urgency
        urgency_hours = {"critical": 12, "high": 24, "medium": 36, "low": 48}
        required_by = now + timedelta(hours=urgency_hours.get(urgency, 48))

        requests.append({
            "dc_id": dc_id,
            "dc_code": fc.get("dc_code", "UNKNOWN"),
            "sku_id": sku_id,
            "sku_code": sku_code,
            "sku_name": fc.get("sku_name", "Unknown SKU"),
            "requested_quantity": requested_qty,
            "urgency": urgency,
            "required_by": required_by.isoformat(),
            "current_stock": effective_stock,
            "forecast_48h": round(forecast_48h, 1),
            "hours_coverage": round(hours_coverage, 1),
        })

    # Sort by urgency (critical first) then by hours_coverage ascending
    urgency_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    requests.sort(key=lambda x: (urgency_order.get(x["urgency"], 4), x["hours_coverage"]))

    return requests
