from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.product import Product
from app.models.purchase import Purchase
from app.models.sale import Sale
from app.models.user import User


router = APIRouter()


def resolve_range(from_date: date | None, to_date: date | None) -> tuple[date, date, datetime, datetime]:
    today = datetime.now(timezone.utc).date()
    end_date = to_date or today
    start_date = from_date or (end_date - timedelta(days=29))

    if start_date > end_date:
        raise HTTPException(status_code=400, detail="Rango de fechas invalido")
    if (end_date - start_date).days > 365:
        raise HTTPException(status_code=400, detail="El rango maximo permitido es 365 dias")

    start_dt = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
    end_dt = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=timezone.utc)
    return start_date, end_date, start_dt, end_dt


@router.get("/summary")
def summary(
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("dashboard:view")),
) -> dict:
    range_from, range_to, start_dt, end_dt = resolve_range(from_date, to_date)

    total_articles = db.scalar(select(func.count(Product.id))) or 0
    low_stock = db.scalar(select(func.count(Product.id)).where(Product.stock <= 5)) or 0
    sales_total = db.scalar(
        select(func.coalesce(func.sum(Sale.total_usd), 0))
        .where(Sale.created_at >= start_dt)
        .where(Sale.created_at < end_dt)
        .where(Sale.is_voided.is_not(True))
    )
    purchases_total = db.scalar(
        select(func.coalesce(func.sum(Purchase.total_usd), 0))
        .where(Purchase.created_at >= start_dt)
        .where(Purchase.created_at < end_dt)
    )
    margin = float(sales_total or 0) - float(purchases_total or 0)

    return {
        "brand": "RIDAX",
        "range_from": range_from.isoformat(),
        "range_to": range_to.isoformat(),
        "total_articles": total_articles,
        "low_stock_articles": low_stock,
        "sales_usd": float(sales_total or 0),
        "purchases_usd": float(purchases_total or 0),
        "gross_margin_usd": round(margin, 2),
        "monthly_sales_usd": float(sales_total or 0),
        "monthly_purchases_usd": float(purchases_total or 0),
    }


@router.get("/timeseries")
def timeseries(
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("dashboard:view")),
) -> dict:
    range_from, range_to, start_dt, end_dt = resolve_range(from_date, to_date)

    sales_rows = db.execute(
        select(
            func.date_trunc("day", Sale.created_at).label("day"),
            func.coalesce(func.sum(Sale.total_usd), 0).label("amount"),
        )
        .where(Sale.created_at >= start_dt)
        .where(Sale.created_at < end_dt)
        .where(Sale.is_voided.is_not(True))
        .group_by(func.date_trunc("day", Sale.created_at))
        .order_by(func.date_trunc("day", Sale.created_at))
    ).all()

    purchase_rows = db.execute(
        select(
            func.date_trunc("day", Purchase.created_at).label("day"),
            func.coalesce(func.sum(Purchase.total_usd), 0).label("amount"),
        )
        .where(Purchase.created_at >= start_dt)
        .where(Purchase.created_at < end_dt)
        .group_by(func.date_trunc("day", Purchase.created_at))
        .order_by(func.date_trunc("day", Purchase.created_at))
    ).all()

    sales_map = {row.day.date().isoformat(): float(row.amount or 0) for row in sales_rows}
    purchases_map = {row.day.date().isoformat(): float(row.amount or 0) for row in purchase_rows}

    points = []
    current = range_from
    while current <= range_to:
        key = current.isoformat()
        sales_value = round(sales_map.get(key, 0.0), 2)
        purchases_value = round(purchases_map.get(key, 0.0), 2)
        points.append(
            {
                "date": key,
                "sales_usd": sales_value,
                "purchases_usd": purchases_value,
                "gross_margin_usd": round(sales_value - purchases_value, 2),
            }
        )
        current += timedelta(days=1)

    return {
        "range_from": range_from.isoformat(),
        "range_to": range_to.isoformat(),
        "group_by": "day",
        "points": points,
    }
