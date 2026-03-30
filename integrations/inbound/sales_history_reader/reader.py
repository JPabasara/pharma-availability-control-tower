"""Sales history reader — reads last 7 days and computes 48-hour demand forecast per DC per SKU."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from storage.models import SalesHistoryRecord, DC, SKU


def get_recent_sales(session: Session, days: int = 7) -> list[SalesHistoryRecord]:
    """Fetch sales history records from the last N days."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    return (
        session.query(SalesHistoryRecord)
        .filter(SalesHistoryRecord.sale_date >= cutoff)
        .order_by(SalesHistoryRecord.sale_date.desc())
        .all()
    )


def compute_48h_forecasts(session: Session, days: int = 7) -> list[dict]:
    """Compute 48-hour demand forecast per DC per SKU.

    Algorithm: avg daily sales over last N days × 2 (for 48 hours)

    Returns:
        [
            {
                dc_id: int,
                dc_code: str,
                dc_name: str,
                sku_id: int,
                sku_code: str,
                sku_name: str,
                total_sold_7d: int,
                daily_avg: float,
                forecast_48h: float
            }
        ]
    """
    cutoff = datetime.utcnow() - timedelta(days=days)

    # Aggregate total sold per (dc_id, sku_id) over the period
    rows = (
        session.query(
            SalesHistoryRecord.dc_id,
            SalesHistoryRecord.sku_id,
            func.sum(SalesHistoryRecord.quantity_sold).label("total_sold"),
            func.count(SalesHistoryRecord.id).label("record_count"),
        )
        .filter(SalesHistoryRecord.sale_date >= cutoff)
        .group_by(SalesHistoryRecord.dc_id, SalesHistoryRecord.sku_id)
        .all()
    )

    forecasts = []
    for row in rows:
        dc = session.query(DC).filter(DC.id == row.dc_id).first()
        sku = session.query(SKU).filter(SKU.id == row.sku_id).first()

        total_sold = int(row.total_sold)
        daily_avg = total_sold / days
        forecast_48h = daily_avg * 2

        forecasts.append({
            "dc_id": row.dc_id,
            "dc_code": dc.code if dc else "UNKNOWN",
            "dc_name": dc.name if dc else "Unknown DC",
            "sku_id": row.sku_id,
            "sku_code": sku.code if sku else "UNKNOWN",
            "sku_name": sku.name if sku else "Unknown SKU",
            "total_sold_7d": total_sold,
            "daily_avg": round(daily_avg, 2),
            "forecast_48h": round(forecast_48h, 2),
        })

    return forecasts


def to_contract(session: Session) -> list[dict]:
    """Return the 48h forecast as the engine-ready contract.

    This is the primary output used by M2 to determine replenishment needs.
    """
    return compute_48h_forecasts(session)
