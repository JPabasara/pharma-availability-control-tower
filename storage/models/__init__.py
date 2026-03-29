"""Central model registry — imports all models so Alembic can find them."""

from storage.models.base import Base, IdMixin, TimestampMixin

# Master tables
from storage.models.masters import SKU, DC, Lorry, RouteEdge, Vessel

# Snapshot tables
from storage.models.snapshots import (
    ManifestSnapshot,
    ManifestLine,
    WarehouseStockSnapshot,
    WarehouseStockItem,
    DCStockSnapshot,
    DCStockItem,
    SalesHistoryRecord,
    LorryStateSnapshot,
    LorryStateItem,
    ETASnapshot,
)

# Engine run tables
from storage.models.engine_runs import (
    EngineRun,
    M1Result,
    M2Request,
    M3PlanVersion,
    M3PlanStop,
    M3PlanItem,
)

# Planner flow tables
from storage.models.planner import PlannerDecision, OverrideReason

# Demo state tables
from storage.models.demo_state import (
    DemoReservation,
    DemoTransfer,
    DemoArrivalEvent,
    DemoStockProjection,
)

# Audit table
from storage.models.audit import AuditLog

__all__ = [
    "Base",
    "IdMixin",
    "TimestampMixin",
    # Masters
    "SKU",
    "DC",
    "Lorry",
    "RouteEdge",
    "Vessel",
    # Snapshots
    "ManifestSnapshot",
    "ManifestLine",
    "WarehouseStockSnapshot",
    "WarehouseStockItem",
    "DCStockSnapshot",
    "DCStockItem",
    "SalesHistoryRecord",
    "LorryStateSnapshot",
    "LorryStateItem",
    "ETASnapshot",
    # Engine runs
    "EngineRun",
    "M1Result",
    "M2Request",
    "M3PlanVersion",
    "M3PlanStop",
    "M3PlanItem",
    # Planner
    "PlannerDecision",
    "OverrideReason",
    # Demo state
    "DemoReservation",
    "DemoTransfer",
    "DemoArrivalEvent",
    "DemoStockProjection",
    # Audit
    "AuditLog",
]
