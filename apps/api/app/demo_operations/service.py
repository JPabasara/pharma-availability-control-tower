"""Business actions for hosted demo operations."""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

from sqlalchemy import desc
from sqlalchemy.orm import Session, joinedload

from apps.api.app.dependencies.business_time import get_planning_dates
from integrations.inbound.lorry_state_reader import reader as lorry_reader
from storage.models import (
    AuditLog,
    DC,
    DCStockItem,
    DCStockSnapshot,
    DemoArrivalEvent,
    DemoLorryDayState,
    DemoReservation,
    DemoTransfer,
    Lorry,
    M3PlanRun,
    M3PlanStop,
    M3PlanVersion,
    ManifestLine,
    ManifestSnapshot,
    SalesHistoryRecord,
    SKU,
    Vessel,
    WarehouseStockItem,
    WarehouseStockSnapshot,
)


def upload_manifest(
    session: Session,
    *,
    manifest_name: str,
    vessel_id: int,
    csv_bytes: bytes,
    actor: str = "demo-ops",
) -> dict:
    vessel = session.query(Vessel).filter(Vessel.id == vessel_id).first()
    if not vessel:
        return {"success": False, "message": f"Vessel {vessel_id} not found."}

    try:
        text = csv_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        return {"success": False, "message": "Manifest CSV must be UTF-8 encoded."}

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or "sku_code" not in reader.fieldnames or "quantity" not in reader.fieldnames:
        return {"success": False, "message": "Manifest CSV must include sku_code and quantity columns."}

    rows: list[tuple[SKU, int]] = []
    for index, row in enumerate(reader, start=2):
        sku_code = (row.get("sku_code") or "").strip()
        quantity_raw = (row.get("quantity") or "").strip()
        if not sku_code or not quantity_raw:
            return {"success": False, "message": f"Row {index} is missing sku_code or quantity."}
        sku = session.query(SKU).filter(SKU.code == sku_code).first()
        if not sku:
            return {"success": False, "message": f"Row {index}: SKU code {sku_code} not found."}
        try:
            quantity = int(quantity_raw)
        except ValueError:
            return {"success": False, "message": f"Row {index}: quantity must be an integer."}
        if quantity <= 0:
            return {"success": False, "message": f"Row {index}: quantity must be positive."}
        rows.append((sku, quantity))

    if not rows:
        return {"success": False, "message": "Manifest CSV contains no valid rows."}

    now = datetime.now(timezone.utc)
    manifest = ManifestSnapshot(
        manifest_name=manifest_name.strip() or "Unnamed Manifest",
        vessel_id=vessel_id,
        snapshot_time=now,
        status="active",
    )
    session.add(manifest)
    session.flush()

    for sku, quantity in rows:
        session.add(
            ManifestLine(
                manifest_snapshot_id=manifest.id,
                sku_id=sku.id,
                quantity=quantity,
                reefer_required=sku.reefer_required,
            )
        )

    session.add(
        DemoArrivalEvent(
            event_type="manifest_upload",
            reference_id=manifest.id,
            event_time=now,
            details={
                "manifest_name": manifest.manifest_name,
                "vessel_id": vessel.id,
                "vessel_code": vessel.code,
                "lines_uploaded": len(rows),
            },
        )
    )
    session.add(
        AuditLog(
            entity_type="manifest_snapshot",
            entity_id=manifest.id,
            action="uploaded",
            actor=actor,
            timestamp=now,
            details={
                "manifest_name": manifest.manifest_name,
                "vessel_id": vessel.id,
                "lines_uploaded": len(rows),
            },
        )
    )
    session.commit()
    return {
        "success": True,
        "message": f"Manifest {manifest.manifest_name} uploaded successfully.",
        "manifest_id": manifest.id,
        "line_count": len(rows),
    }


def arrive_manifest(session: Session, manifest_id: int, actor: str = "demo-ops") -> dict:
    manifest = (
        session.query(ManifestSnapshot)
        .options(joinedload(ManifestSnapshot.lines))
        .filter(ManifestSnapshot.id == manifest_id)
        .first()
    )
    if not manifest:
        return {"success": False, "message": f"Manifest {manifest_id} not found."}
    return _arrive_manifest_record(session, manifest, actor=actor)


def arrive_active_manifests(
    session: Session,
    *,
    vessel_id: int | None = None,
    actor: str = "system_cli",
) -> dict:
    query = (
        session.query(ManifestSnapshot)
        .options(joinedload(ManifestSnapshot.lines))
        .filter(ManifestSnapshot.status == "active")
    )
    if vessel_id is not None:
        query = query.filter(ManifestSnapshot.vessel_id == vessel_id)

    manifests = query.order_by(ManifestSnapshot.snapshot_time).all()
    results = []
    total_skus_updated = 0
    total_quantity_added = 0
    for manifest in manifests:
        result = _arrive_manifest_record(session, manifest, actor=actor, auto_commit=False)
        if result["success"]:
            total_skus_updated += result.get("total_skus_updated", 0)
            total_quantity_added += result.get("total_quantity_added", 0)
            results.append(result)

    session.commit()
    return {
        "success": True,
        "message": f"Processed {len(results)} vessel arrival(s).",
        "arrived": len(results),
        "total_skus_updated": total_skus_updated,
        "total_quantity_added": total_quantity_added,
        "vessels": [result["vessel"] for result in results],
    }


def post_dc_sale(
    session: Session,
    *,
    dc_id: int,
    sku_id: int,
    quantity: int,
    actor: str = "demo-ops",
) -> dict:
    if quantity <= 0:
        return {"success": False, "message": "Sale quantity must be positive."}

    dc = session.query(DC).filter(DC.id == dc_id).first()
    sku = session.query(SKU).filter(SKU.id == sku_id).first()
    if not dc or not sku:
        return {"success": False, "message": "DC or SKU not found."}

    latest_snapshot = (
        session.query(DCStockSnapshot)
        .options(joinedload(DCStockSnapshot.items))
        .filter(DCStockSnapshot.dc_id == dc_id)
        .order_by(desc(DCStockSnapshot.snapshot_time))
        .first()
    )
    if not latest_snapshot:
        return {"success": False, "message": f"No DC stock snapshot found for DC {dc.code}."}

    stock_item = next((item for item in latest_snapshot.items if item.sku_id == sku_id), None)
    if not stock_item or stock_item.physical_quantity < quantity:
        available = stock_item.physical_quantity if stock_item else 0
        return {
            "success": False,
            "message": f"DC {dc.code} has insufficient physical stock for {sku.code}. Available: {available}.",
            "dc_id": dc_id,
            "dc_code": dc.code,
            "sku_id": sku_id,
            "sku_code": sku.code,
            "available_quantity": available,
            "requested_quantity": quantity,
            "shortfall_quantity": max(quantity - available, 0),
        }

    now = datetime.now(timezone.utc)
    available_before = stock_item.physical_quantity
    stock_item.physical_quantity -= quantity
    stock_item.effective_quantity = stock_item.physical_quantity + stock_item.in_transit_quantity
    session.add(
        SalesHistoryRecord(
            dc_id=dc_id,
            sku_id=sku_id,
            sale_date=now,
            quantity_sold=quantity,
        )
    )
    session.add(
        DemoArrivalEvent(
            event_type="dc_sale",
            reference_id=dc_id,
            event_time=now,
            details={
                "dc_code": dc.code,
                "sku_code": sku.code,
                "quantity_sold": quantity,
            },
        )
    )
    session.add(
        AuditLog(
            entity_type="dc_stock",
            entity_id=dc_id,
            action="sale_posted",
            actor=actor,
            timestamp=now,
            details={"sku_code": sku.code, "quantity_sold": quantity},
        )
    )
    session.commit()
    return {
        "success": True,
        "message": f"Recorded sale of {quantity} units of {sku.code} at {dc.code}.",
        "dc_id": dc_id,
        "dc_code": dc.code,
        "sku_id": sku_id,
        "sku_code": sku.code,
        "available_before": available_before,
        "remaining_physical": stock_item.physical_quantity,
        "quantity_sold": quantity,
    }


def get_lorry_horizon(session: Session) -> dict | None:
    return lorry_reader.get_latest_contract(session)


def set_lorry_availability(
    session: Session,
    *,
    lorry_id: int,
    dispatch_day: int,
    status: str,
    actor: str = "demo-ops",
) -> dict:
    if status not in {"available", "unavailable"}:
        return {"success": False, "message": "Status must be available or unavailable."}
    if dispatch_day not in {1, 2}:
        return {"success": False, "message": "dispatch_day must be 1 or 2."}

    lorry = session.query(Lorry).filter(Lorry.id == lorry_id).first()
    if not lorry:
        return {"success": False, "message": f"Lorry {lorry_id} not found."}

    planning_dates = get_planning_dates()
    target_date = planning_dates[dispatch_day - 1]
    existing = (
        session.query(DemoLorryDayState)
        .filter(
            DemoLorryDayState.lorry_id == lorry_id,
            DemoLorryDayState.business_date == target_date,
        )
        .first()
    )
    if existing and existing.status == "assigned":
        return {
            "success": False,
            "message": f"Lorry {lorry.registration} is already assigned on Day {dispatch_day}.",
            "dispatch_day": dispatch_day,
            "business_date": target_date.isoformat(),
            "status": existing.status,
        }

    now = datetime.now(timezone.utc)
    previous_status = existing.status if existing else lorry.status
    if existing:
        existing.status = status
        existing.source = "manual"
    else:
        session.add(
            DemoLorryDayState(
                lorry_id=lorry_id,
                business_date=target_date,
                status=status,
                source="manual",
            )
        )

    session.add(
        AuditLog(
            entity_type="lorry",
            entity_id=lorry_id,
            action=f"set_{status}",
            actor=actor,
            timestamp=now,
            details={
                "dispatch_day": dispatch_day,
                "business_date": target_date.isoformat(),
                "previous_status": previous_status,
                "new_status": status,
            },
        )
    )
    session.commit()
    return {
        "success": True,
        "message": f"Lorry {lorry.registration} set to {status} on Day {dispatch_day}.",
        "lorry_id": lorry_id,
        "registration": lorry.registration,
        "dispatch_day": dispatch_day,
        "business_date": target_date.isoformat(),
        "previous_status": previous_status,
        "status": status,
    }


def get_open_execution_stops(session: Session) -> list[dict]:
    transfer_rows = (
        session.query(DemoTransfer)
        .filter(DemoTransfer.status == "in_transit", DemoTransfer.plan_stop_id.isnot(None))
        .order_by(DemoTransfer.dispatched_at.asc())
        .all()
    )
    if not transfer_rows:
        return []

    stop_ids = sorted({row.plan_stop_id for row in transfer_rows if row.plan_stop_id})
    stops = (
        session.query(M3PlanStop)
        .options(joinedload(M3PlanStop.run).joinedload(M3PlanRun.plan_version))
        .filter(M3PlanStop.id.in_(stop_ids))
        .all()
    )
    stop_lookup = {stop.id: stop for stop in stops}

    grouped: dict[int, dict] = {}
    for transfer in transfer_rows:
        stop = stop_lookup.get(transfer.plan_stop_id)
        if not stop:
            continue
        run = stop.run
        lorry = session.query(Lorry).filter(Lorry.id == run.lorry_id).first()
        dc = session.query(DC).filter(DC.id == stop.dc_id).first()
        sku = session.query(SKU).filter(SKU.id == transfer.sku_id).first()

        bucket = grouped.setdefault(
            stop.id,
            {
                "plan_stop_id": stop.id,
                "plan_version_id": run.plan_version_id,
                "plan_run_id": run.id,
                "dispatch_day": run.dispatch_day,
                "lorry_id": run.lorry_id,
                "registration": lorry.registration if lorry else "UNKNOWN",
                "lorry_type": lorry.lorry_type if lorry else "unknown",
                "dc_id": stop.dc_id,
                "dc_code": dc.code if dc else "UNKNOWN",
                "dc_name": dc.name if dc else "Unknown",
                "stop_sequence": stop.stop_sequence,
                "items": [],
            },
        )
        bucket["items"].append({
            "transfer_id": transfer.id,
            "sku_id": transfer.sku_id,
            "sku_code": sku.code if sku else "UNKNOWN",
            "sku_name": sku.name if sku else "Unknown",
            "quantity": transfer.quantity,
        })

    return list(grouped.values())


def arrive_stop(session: Session, plan_stop_id: int, actor: str = "demo-ops") -> dict:
    stop = (
        session.query(M3PlanStop)
        .options(joinedload(M3PlanStop.run))
        .filter(M3PlanStop.id == plan_stop_id)
        .first()
    )
    if not stop:
        return {"success": False, "message": f"Plan stop {plan_stop_id} not found."}

    transfers = (
        session.query(DemoTransfer)
        .filter(DemoTransfer.plan_stop_id == plan_stop_id, DemoTransfer.status == "in_transit")
        .all()
    )
    if not transfers:
        return {"success": False, "message": f"Plan stop {plan_stop_id} has no in-transit transfers."}

    latest_dc_snapshot = (
        session.query(DCStockSnapshot)
        .options(joinedload(DCStockSnapshot.items))
        .filter(DCStockSnapshot.dc_id == stop.dc_id)
        .order_by(desc(DCStockSnapshot.snapshot_time))
        .first()
    )
    if not latest_dc_snapshot:
        latest_dc_snapshot = DCStockSnapshot(dc_id=stop.dc_id, snapshot_time=datetime.now(timezone.utc))
        session.add(latest_dc_snapshot)
        session.flush()

    now = datetime.now(timezone.utc)
    dc_items_by_sku = {item.sku_id: item for item in latest_dc_snapshot.items}
    total_quantity = 0

    for transfer in transfers:
        dc_item = dc_items_by_sku.get(transfer.sku_id)
        if not dc_item:
            dc_item = DCStockItem(
                snapshot_id=latest_dc_snapshot.id,
                sku_id=transfer.sku_id,
                physical_quantity=0,
                in_transit_quantity=0,
                effective_quantity=0,
            )
            session.add(dc_item)
            session.flush()
            dc_items_by_sku[transfer.sku_id] = dc_item

        dc_item.physical_quantity += transfer.quantity
        dc_item.effective_quantity = dc_item.physical_quantity + dc_item.in_transit_quantity
        transfer.status = "arrived"
        transfer.arrived_at = now
        total_quantity += transfer.quantity

    reservations = (
        session.query(DemoReservation)
        .filter(DemoReservation.plan_stop_id == plan_stop_id, DemoReservation.status == "active")
        .all()
    )
    for reservation in reservations:
        reservation.status = "released"

    dc = session.query(DC).filter(DC.id == stop.dc_id).first()
    lorry = session.query(Lorry).filter(Lorry.id == stop.run.lorry_id).first()
    session.add(
        DemoArrivalEvent(
            event_type="lorry_arrival",
            reference_id=plan_stop_id,
            event_time=now,
            details={
                "plan_version_id": stop.run.plan_version_id,
                "plan_run_id": stop.run.id,
                "dispatch_day": stop.run.dispatch_day,
                "dc_code": dc.code if dc else "UNKNOWN",
                "registration": lorry.registration if lorry else "UNKNOWN",
                "total_quantity": total_quantity,
            },
        )
    )
    session.add(
        AuditLog(
            entity_type="plan_stop",
            entity_id=plan_stop_id,
            action="arrived",
            actor=actor,
            timestamp=now,
            details={
                "dc_code": dc.code if dc else "UNKNOWN",
                "registration": lorry.registration if lorry else "UNKNOWN",
                "total_quantity": total_quantity,
                "reservations_released": len(reservations),
            },
        )
    )
    session.commit()

    return {
        "success": True,
        "message": f"Stop {plan_stop_id} arrived successfully.",
        "plan_stop_id": plan_stop_id,
        "transfers_arrived": len(transfers),
        "reservations_released": len(reservations),
        "total_quantity_moved": total_quantity,
    }


def arrive_open_stops(
    session: Session,
    *,
    dc_id: int | None = None,
    lorry_id: int | None = None,
    actor: str = "system_cli",
) -> dict:
    open_stops = get_open_execution_stops(session)
    if dc_id is not None:
        open_stops = [stop for stop in open_stops if stop["dc_id"] == dc_id]
    if lorry_id is not None:
        open_stops = [stop for stop in open_stops if stop["lorry_id"] == lorry_id]

    results = []
    total_quantity = 0
    total_reservations = 0
    for stop in open_stops:
        result = arrive_stop(session, stop["plan_stop_id"], actor=actor)
        if result["success"]:
            results.append(result)
            total_quantity += result["total_quantity_moved"]
            total_reservations += result["reservations_released"]

    return {
        "success": True,
        "message": f"Processed {len(results)} lorry arrival(s).",
        "arrived": len(results),
        "total_quantity_moved": total_quantity,
        "total_reservations_released": total_reservations,
        "stops": results,
    }


def _arrive_manifest_record(
    session: Session,
    manifest: ManifestSnapshot,
    *,
    actor: str,
    auto_commit: bool = True,
) -> dict:
    if manifest.status != "active":
        return {
            "success": False,
            "message": f"Manifest {manifest.id} is already {manifest.status}.",
        }

    latest_wh = (
        session.query(WarehouseStockSnapshot)
        .options(joinedload(WarehouseStockSnapshot.items))
        .order_by(desc(WarehouseStockSnapshot.snapshot_time))
        .first()
    )
    if not latest_wh:
        return {"success": False, "message": "No warehouse stock snapshot found."}

    now = datetime.now(timezone.utc)
    wh_items_by_sku = {item.sku_id: item for item in latest_wh.items}
    vessel = session.query(Vessel).filter(Vessel.id == manifest.vessel_id).first()
    manifest_details = []

    for line in manifest.lines:
        sku = session.query(SKU).filter(SKU.id == line.sku_id).first()
        if line.sku_id in wh_items_by_sku:
            wh_item = wh_items_by_sku[line.sku_id]
        else:
            wh_item = WarehouseStockItem(
                snapshot_id=latest_wh.id,
                sku_id=line.sku_id,
                physical_quantity=0,
                reserved_quantity=0,
                effective_quantity=0,
            )
            session.add(wh_item)
            session.flush()
            wh_items_by_sku[line.sku_id] = wh_item

        old_qty = wh_item.physical_quantity
        wh_item.physical_quantity += line.quantity
        wh_item.effective_quantity = wh_item.physical_quantity - wh_item.reserved_quantity

        manifest_details.append({
            "sku_id": line.sku_id,
            "sku_code": sku.code if sku else "UNKNOWN",
            "quantity_added": line.quantity,
            "old_physical": old_qty,
            "new_physical": wh_item.physical_quantity,
        })

    manifest.status = "arrived"
    session.add(
        DemoArrivalEvent(
            event_type="vessel_arrival",
            reference_id=manifest.id,
            event_time=now,
            details={
                "manifest_name": manifest.manifest_name,
                "vessel_id": manifest.vessel_id,
                "vessel_name": vessel.name if vessel else f"Vessel #{manifest.vessel_id}",
                "vessel_code": vessel.code if vessel else "UNKNOWN",
                "lines_processed": len(manifest.lines),
                "total_quantity": sum(detail["quantity_added"] for detail in manifest_details),
            },
        )
    )
    session.add(
        AuditLog(
            entity_type="manifest_snapshot",
            entity_id=manifest.id,
            action="vessel_arrived",
            actor=actor,
            timestamp=now,
            details={
                "manifest_name": manifest.manifest_name,
                "total_quantity_added": sum(detail["quantity_added"] for detail in manifest_details),
            },
        )
    )

    if auto_commit:
        session.commit()

    return {
        "success": True,
        "message": f"Manifest {manifest.id} arrived successfully.",
        "arrived": 1,
        "manifest_id": manifest.id,
        "total_skus_updated": len(manifest_details),
        "total_quantity_added": sum(detail["quantity_added"] for detail in manifest_details),
        "vessel": {
            "manifest_id": manifest.id,
            "manifest_name": manifest.manifest_name,
            "vessel_id": manifest.vessel_id,
            "vessel_name": vessel.name if vessel else f"Vessel #{manifest.vessel_id}",
            "vessel_code": vessel.code if vessel else "UNKNOWN",
            "lines_processed": len(manifest_details),
            "details": manifest_details,
        },
    }
