"""Engine Bridge — abstracts stub vs real engine routing.

Uses ENGINE_MODE env var to determine which implementation to call:
  - 'stub' (default): Uses contract-compatible stubs
  - 'real': Will route to actual engine implementations (future)
"""

import os


def get_engine_mode() -> str:
    """Get the current engine mode from environment."""
    return os.getenv("ENGINE_MODE", "stub").lower()


def run_m1(
    manifest_lines: list[dict],
    warehouse_stock: dict,
    m2_requests: list[dict],
    sku_metadata: dict,
    etas: list[dict],
) -> list[dict]:
    """Run M1 engine (priority scoring) via the configured engine mode."""
    mode = get_engine_mode()

    if mode == "real":
        # Future: import and call real M1 engine
        raise NotImplementedError("Real M1 engine not yet connected. Set ENGINE_MODE=stub.")

    from apps.api.app.orchestration.stubs.m1_stub import run
    return run(manifest_lines, warehouse_stock, m2_requests, sku_metadata, etas)


def run_m2(
    dc_stock_contracts: list[dict],
    sales_forecasts: list[dict],
) -> list[dict]:
    """Run M2 engine (replenishment request generation) via the configured engine mode."""
    mode = get_engine_mode()

    if mode == "real":
        raise NotImplementedError("Real M2 engine not yet connected. Set ENGINE_MODE=stub.")

    from apps.api.app.orchestration.stubs.m2_stub import run
    return run(dc_stock_contracts, sales_forecasts)


def run_m3(
    m1_results: list[dict],
    m2_requests: list[dict],
    warehouse_stock: dict,
    lorry_state: dict,
    route_graph: list[dict],
) -> list[dict]:
    """Run M3 engine (dispatch plan generation) via the configured engine mode."""
    mode = get_engine_mode()

    if mode == "real":
        raise NotImplementedError("Real M3 engine not yet connected. Set ENGINE_MODE=stub.")

    from apps.api.app.orchestration.stubs.m3_stub import run
    return run(m1_results, m2_requests, warehouse_stock, lorry_state, route_graph)
