"""Snapshot capture and reread services for planner Inputs refresh actions."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import desc
from sqlalchemy.orm import Session, joinedload

from integrations.inbound.eta_provider import provider as eta_provider
from integrations.inbound.manifest_reader import reader as manifest_reader
from integrations.inbound.sales_history_reader import reader as sales_reader
from storage.models import (
    DCStockItem,
    DCStockSnapshot,
    LorryStateItem,
    LorryStateSnapshot,
    WarehouseStockItem,
    WarehouseStockSnapshot,
)

INPUT_FAMILIES = ("manifests", "warehouse", "dc", "sales", "lorries", "etas")


def refresh_all(session: Session) -> dict:
    """Run the mixed-mode refresh for every Inputs family."""
    now = datetime.now(timezone.utc)
    families = {
        "manifests": _reload_manifests(session, generated_at=now),
        "warehouse": _capture_warehouse_snapshot(session, captured_at=now),
        "dc": _capture_dc_snapshots(session, captured_at=now),
        "sales": _reload_sales(session, generated_at=now),
        "lorries": _capture_lorry_snapshot(session, captured_at=now),
        "etas": _refresh_etas(session),
    }
    session.commit()
    return {
        "success": True,
        "scope": "all",
        "generated_at": now.isoformat(),
        "message": "Inputs refreshed across all families.",
        "families": families,
    }


def refresh_family(session: Session, family: str) -> dict:
    """Refresh one Inputs family using the mixed-mode family policy."""
    if family not in INPUT_FAMILIES:
        return {
            "success": False,
            "message": f"Unknown input family '{family}'.",
            "family": family,
        }

    now = datetime.now(timezone.utc)
    if family == "manifests":
        result = _reload_manifests(session, generated_at=now)
    elif family == "warehouse":
        result = _capture_warehouse_snapshot(session, captured_at=now)
    elif family == "dc":
        result = _capture_dc_snapshots(session, captured_at=now)
    elif family == "sales":
        result = _reload_sales(session, generated_at=now)
    elif family == "lorries":
        result = _capture_lorry_snapshot(session, captured_at=now)
    else:
        result = _refresh_etas(session)

    session.commit()
    return {
        "success": True,
        "scope": family,
        "generated_at": now.isoformat(),
        "message": f"{family.title()} refreshed successfully.",
        "families": {family: result},
    }


def _reload_manifests(session: Session, *, generated_at: datetime) -> dict:
    manifests = manifest_reader.get_all_active_contracts(session)
    latest_snapshot_time = manifests[0]["snapshot_time"] if manifests else None
    return {
        "family": "manifests",
        "mode": "reloaded",
        "count": len(manifests),
        "latest_snapshot_time": latest_snapshot_time,
        "generated_at": generated_at.isoformat(),
    }


def _reload_sales(session: Session, *, generated_at: datetime) -> dict:
    forecasts = sales_reader.to_contract(session)
    return {
        "family": "sales",
        "mode": "reloaded",
        "count": len(forecasts),
        "generated_at": generated_at.isoformat(),
        "lookback_days": 30,
    }


def _capture_warehouse_snapshot(session: Session, *, captured_at: datetime) -> dict:
    latest = (
        session.query(WarehouseStockSnapshot)
        .options(joinedload(WarehouseStockSnapshot.items))
        .order_by(desc(WarehouseStockSnapshot.snapshot_time))
        .first()
    )
    if latest is None:
        raise ValueError("No warehouse stock snapshot found.")

    snapshot = WarehouseStockSnapshot(snapshot_time=captured_at)
    session.add(snapshot)
    session.flush()

    for item in latest.items:
        session.add(
            WarehouseStockItem(
                snapshot_id=snapshot.id,
                sku_id=item.sku_id,
                physical_quantity=item.physical_quantity,
                reserved_quantity=item.reserved_quantity,
                effective_quantity=item.physical_quantity - item.reserved_quantity,
            )
        )

    session.flush()
    return {
        "family": "warehouse",
        "mode": "captured",
        "snapshot_id": snapshot.id,
        "snapshot_time": snapshot.snapshot_time.isoformat(),
        "item_count": len(latest.items),
    }


def _capture_dc_snapshots(session: Session, *, captured_at: datetime) -> dict:
    latest_by_dc: list[DCStockSnapshot] = []
    dc_ids = [value[0] for value in session.query(DCStockSnapshot.dc_id).distinct().all()]
    for dc_id in dc_ids:
        latest = (
            session.query(DCStockSnapshot)
            .options(joinedload(DCStockSnapshot.items))
            .filter(DCStockSnapshot.dc_id == dc_id)
            .order_by(desc(DCStockSnapshot.snapshot_time))
            .first()
        )
        if latest:
            latest_by_dc.append(latest)

    if not latest_by_dc:
        raise ValueError("No DC stock snapshots found.")

    snapshot_ids: list[int] = []
    item_count = 0
    for latest in latest_by_dc:
        snapshot = DCStockSnapshot(dc_id=latest.dc_id, snapshot_time=captured_at)
        session.add(snapshot)
        session.flush()
        snapshot_ids.append(snapshot.id)

        for item in latest.items:
            session.add(
                DCStockItem(
                    snapshot_id=snapshot.id,
                    sku_id=item.sku_id,
                    physical_quantity=item.physical_quantity,
                    in_transit_quantity=item.in_transit_quantity,
                    effective_quantity=item.physical_quantity + item.in_transit_quantity,
                )
            )
            item_count += 1

    session.flush()
    return {
        "family": "dc",
        "mode": "captured",
        "snapshot_count": len(snapshot_ids),
        "snapshot_ids": snapshot_ids,
        "snapshot_time": captured_at.isoformat(),
        "item_count": item_count,
    }


def _capture_lorry_snapshot(session: Session, *, captured_at: datetime) -> dict:
    latest = (
        session.query(LorryStateSnapshot)
        .options(joinedload(LorryStateSnapshot.items))
        .order_by(desc(LorryStateSnapshot.snapshot_time))
        .first()
    )
    if latest is None:
        raise ValueError("No lorry state snapshot found.")

    snapshot = LorryStateSnapshot(snapshot_time=captured_at)
    session.add(snapshot)
    session.flush()

    for item in latest.items:
        session.add(
            LorryStateItem(
                snapshot_id=snapshot.id,
                lorry_id=item.lorry_id,
                status=item.status,
            )
        )

    session.flush()
    return {
        "family": "lorries",
        "mode": "captured",
        "snapshot_id": snapshot.id,
        "snapshot_time": snapshot.snapshot_time.isoformat(),
        "lorry_count": len(latest.items),
    }


def _refresh_etas(session: Session) -> dict:
    result = eta_provider.refresh_all_active_etas(session, auto_commit=False)
    return {
        "family": "etas",
        "mode": "captured",
        "count": result["count"],
        "latest_fetched_at": result["latest_fetched_at"],
    }
