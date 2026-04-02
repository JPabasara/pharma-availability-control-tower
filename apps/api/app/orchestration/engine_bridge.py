"""Engine Bridge — abstracts stub vs real engine routing.

Supports per-engine mode switching via:
  M1_ENGINE_MODE, M2_ENGINE_MODE, M3_ENGINE_MODE

Falls back to ENGINE_MODE if per-engine flag is absent.
Default is 'stub' if nothing is set.
"""

import os
import logging

logger = logging.getLogger(__name__)


def get_engine_mode(engine: str | None = None) -> str:
    """Get engine mode. If engine is specified (m1/m2/m3), check per-engine flag first."""
    if engine:
        per_engine = os.getenv(f"{engine.upper()}_ENGINE_MODE")
        if per_engine:
            return per_engine.lower()
    return os.getenv("ENGINE_MODE", "stub").lower()


def run_m1(
    manifest_lines: list[dict],
    warehouse_stock: dict,
    m2_requests: list[dict],
    sku_metadata: dict,
    etas: list[dict],
) -> list[dict]:
    """Run M1 engine (priority scoring) via the configured engine mode."""
    mode = get_engine_mode("m1")
    logger.info(f"M1 engine mode: {mode}")

    if mode == "real":
        from apps.api.app.orchestration.real.m1_real import run
        return run(manifest_lines, warehouse_stock, m2_requests, sku_metadata, etas)

    from apps.api.app.orchestration.stubs.m1_stub import run
    return run(manifest_lines, warehouse_stock, m2_requests, sku_metadata, etas)


def run_m2(
    dc_stock_contracts: list[dict],
    sales_forecasts: list[dict],
) -> list[dict]:
    """Run M2 engine (replenishment request generation) via the configured engine mode."""
    mode = get_engine_mode("m2")
    logger.info(f"M2 engine mode: {mode}")

    if mode == "real":
        from apps.api.app.orchestration.real.m2_real import run
        return run(dc_stock_contracts, sales_forecasts)

    from apps.api.app.orchestration.stubs.m2_stub import run
    return run(dc_stock_contracts, sales_forecasts)


def run_m3(
    m2_requests: list[dict],
    warehouse_stock: dict,
    lorry_state: dict,
    route_graph: list[dict],
    sku_metadata: dict,
) -> list[dict]:
    """Run M3 engine (dispatch plan generation) via the configured engine mode.

    Note: M3 no longer takes m1_results as input per the integration plan.
    """
    mode = get_engine_mode("m3")
    logger.info(f"M3 engine mode: {mode}")

    if mode == "real":
        from apps.api.app.orchestration.real.m3_real import run
        return run(m2_requests, warehouse_stock, lorry_state, route_graph, sku_metadata)

    # Stub still uses old signature for backward compatibility
    from apps.api.app.orchestration.stubs.m3_stub import run
    return run([], m2_requests, warehouse_stock, lorry_state, route_graph)
