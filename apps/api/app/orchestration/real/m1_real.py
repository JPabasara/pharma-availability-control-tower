"""M1 Real Engine — Mathematical Priority Scoring Engine.

Pure mathematical scoring engine adapted from ml/models/m1_model.py.
Runs against live DB-backed contracts instead of synthetic CSV data.

Adapter responsibilities:
1. Build live runtime features from manifest lines, warehouse stock, M2 requests, ETAs
2. Apply the 5-point mathematical scoring formula
3. Normalize output to planner contract (lowercase bands)
4. Emit score breakdown + raw features for auditability
"""

import logging
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════
# SCORING WEIGHTS (from ml/models/m1_model.py)
# ═══════════════════════════════════════════════════════════════════════

MAX_REEFER_BONUS = 40.0
MAX_M2_DEMAND_BONUS = 35.0
MAX_WH_BUFFER_PENALTY = 20.0
MAX_ETA_DELAY_BONUS = 15.0
MAX_RATIONING_BONUS = 10.0
MAX_SCORE = 100.0

# Priority band thresholds (from Integrate-plan.md)
BAND_THRESHOLDS = [
    (90, "critical"),
    (70, "high"),
    (40, "medium"),
    (0, "low"),
]


# ═══════════════════════════════════════════════════════════════════════
# FEATURE BUILDER — live DB contracts → scoring features
# ═══════════════════════════════════════════════════════════════════════


def _build_features(
    manifest_lines: list[dict],
    warehouse_stock: dict,
    m2_requests: list[dict],
    sku_metadata: dict[int, dict],
    etas: list[dict],
) -> list[dict]:
    """Build per-manifest-line feature dicts from live DB contracts.

    Produces features matching the M1 model expectations:
    - wh_days_of_cover
    - max_m2_urgency (as 0-100 numeric)
    - num_dcs_requesting
    - m2_fulfillment_ratio
    - eta_delay_hours
    - reefer_required
    - manifest_quantity
    - category
    """
    # Build WH stock lookup: sku_id → effective stock
    wh_lookup: dict[int, int] = {}
    if warehouse_stock and "items" in warehouse_stock:
        for item in warehouse_stock["items"]:
            wh_lookup[item["sku_id"]] = item.get("effective", item.get("physical", 0))

    # Build M2 aggregated demand per SKU
    m2_by_sku: dict[int, dict] = {}
    for req in m2_requests:
        sid = req["sku_id"]
        if sid not in m2_by_sku:
            m2_by_sku[sid] = {
                "total_requested": 0,
                "max_urgency_score": 0,
                "num_dcs": set(),
            }
        m2_by_sku[sid]["total_requested"] += req["requested_quantity"]
        m2_by_sku[sid]["num_dcs"].add(req["dc_id"])

        # Map urgency band to numeric score
        urgency_map = {"critical": 100, "high": 70, "medium": 40, "low": 10}
        urgency_val = urgency_map.get(req.get("urgency", "low"), 10)
        # Use trace urgency_score if available (from real M2)
        if "urgency_score" in req:
            urgency_val = req["urgency_score"]
        m2_by_sku[sid]["max_urgency_score"] = max(
            m2_by_sku[sid]["max_urgency_score"], urgency_val
        )

    # Compute ETA delay: proxy from hours_until_arrival
    # Lower hours = arriving sooner = more urgency
    eta_delay_hours = 0.0
    if etas:
        min_hours = min(e.get("hours_until_arrival", 48) for e in etas)
        # If arriving in <24h, treat as positive delay signal
        eta_delay_hours = max(0, 48 - min_hours)

    feature_rows = []
    for line in manifest_lines:
        sku_id = line["sku_id"]
        sku_meta = sku_metadata.get(sku_id, {})
        manifest_qty = line.get("quantity", 0)

        wh_stock = wh_lookup.get(sku_id, 0)
        m2_info = m2_by_sku.get(sku_id, {
            "total_requested": 0,
            "max_urgency_score": 0,
            "num_dcs": set(),
        })

        # Derive M1-specific features
        daily_demand = m2_info["total_requested"] / 2 if m2_info["total_requested"] > 0 else 50
        wh_days_of_cover = wh_stock / daily_demand if daily_demand > 0 else 999

        total_m2_demand = m2_info["total_requested"]
        m2_fulfillment_ratio = (manifest_qty / total_m2_demand) if total_m2_demand > 0 else 1.0

        feature_rows.append({
            "manifest_line_id": line["manifest_line_id"],
            "sku_id": sku_id,
            "sku_code": line.get("sku_code", sku_meta.get("code", "UNKNOWN")),
            "category": sku_meta.get("category", "General"),
            "reefer_required": line.get("reefer_required", sku_meta.get("reefer_required", False)),
            "manifest_quantity": manifest_qty,
            "wh_days_of_cover": wh_days_of_cover,
            "max_m2_urgency": m2_info["max_urgency_score"],
            "num_dcs_requesting": len(m2_info["num_dcs"]),
            "m2_fulfillment_ratio": m2_fulfillment_ratio,
            "eta_delay_hours": eta_delay_hours,
        })

    return feature_rows


# ═══════════════════════════════════════════════════════════════════════
# SCORING ENGINE (adapted from ml/models/m1_model.py)
# ═══════════════════════════════════════════════════════════════════════


def _score_line(features: dict) -> tuple[float, str]:
    """Apply the 5-point mathematical formula to a single manifest line.

    Returns: (priority_score, score_breakdown_text)
    """
    # 1. Reefer Bonus (+40 max)
    score_reefer = MAX_REEFER_BONUS if features["reefer_required"] else 0.0

    # 2. M2 Demand Pull (+35 max)
    score_m2 = (features["max_m2_urgency"] / 100.0) * MAX_M2_DEMAND_BONUS

    # 3. Warehouse Buffer Penalty (-20 max)
    wh_ratio = min(max(features["wh_days_of_cover"] / 7.0, 0), 1.0)
    score_wh_penalty = -(wh_ratio * MAX_WH_BUFFER_PENALTY)

    # 4. ETA Delay Bonus (+15 max)
    eta_ratio = min(max(features["eta_delay_hours"] / 48.0, 0), 1.0)
    score_eta = eta_ratio * MAX_ETA_DELAY_BONUS

    # 5. Rationing Bonus (+10 max)
    score_rationing = 0.0
    if features["m2_fulfillment_ratio"] < 0.5:
        score_rationing = (1.0 - features["m2_fulfillment_ratio"]) * MAX_RATIONING_BONUS

    raw_score = score_reefer + score_m2 + score_wh_penalty + score_eta + score_rationing
    priority_score = round(max(0, min(MAX_SCORE, raw_score)), 1)

    breakdown = (
        f"Reefer(+{score_reefer:.1f}) "
        f"M2(+{score_m2:.1f}) "
        f"WH_Buf({score_wh_penalty:.1f}) "
        f"ETA(+{score_eta:.1f}) "
        f"Ration(+{score_rationing:.1f})"
    )

    return priority_score, breakdown


def _normalize_band(score: float) -> str:
    """Convert numeric score to lowercase priority band per Integrate-plan.md."""
    for threshold, band in BAND_THRESHOLDS:
        if score >= threshold:
            return band
    return "low"


# ═══════════════════════════════════════════════════════════════════════
# MAIN RUN FUNCTION — drop-in replacement for m1_stub.run()
# ═══════════════════════════════════════════════════════════════════════


def run(
    manifest_lines: list[dict],
    warehouse_stock: dict,
    m2_requests: list[dict],
    sku_metadata: dict[int, dict],
    etas: list[dict],
) -> list[dict]:
    """Run M1 real mathematical scoring engine.

    Same contract as m1_stub.run() but adapted from the real M1 model
    with proper feature derivation and score breakdown.
    """
    logger.info("M1 Real Engine: Starting scoring")

    # Build features from live data
    feature_rows = _build_features(
        manifest_lines, warehouse_stock, m2_requests, sku_metadata, etas
    )

    if not feature_rows:
        logger.warning("M1 Real Engine: No manifest lines to score")
        return []

    results = []
    for features in feature_rows:
        priority_score, breakdown = _score_line(features)
        priority_band = _normalize_band(priority_score)

        results.append({
            # Contract fields (same as stub)
            "manifest_line_id": features["manifest_line_id"],
            "sku_id": features["sku_id"],
            "sku_code": features["sku_code"],
            "priority_score": priority_score,
            "priority_band": priority_band,
            "reefer_required": features["reefer_required"],
            # Trace fields
            "score_breakdown": breakdown,
            "raw_features": {
                "category": features["category"],
                "manifest_quantity": features["manifest_quantity"],
                "wh_days_of_cover": round(features["wh_days_of_cover"], 2),
                "max_m2_urgency": features["max_m2_urgency"],
                "num_dcs_requesting": features["num_dcs_requesting"],
                "m2_fulfillment_ratio": round(features["m2_fulfillment_ratio"], 4),
                "eta_delay_hours": features["eta_delay_hours"],
                "reefer_required": features["reefer_required"],
            },
        })

    # Sort by priority score descending
    results.sort(key=lambda x: x["priority_score"], reverse=True)

    logger.info(f"M1 Real Engine: Scored {len(results)} manifest lines")
    return results
