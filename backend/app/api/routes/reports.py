from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.purchase import Purchase
from app.models.sale import Sale
from app.models.system_setting import SystemSetting
from app.models.user import User


router = APIRouter()


@router.get("/kpis")
def kpis(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("reports:view")),
) -> dict:
    now = datetime.now(timezone.utc)
    seven_days_ago = now - timedelta(days=7)
    sales_7d = db.scalar(select(func.coalesce(func.sum(Sale.total_usd), 0)).where(Sale.created_at >= seven_days_ago))
    discount_7d = db.scalar(
        select(func.coalesce(func.sum(Sale.discount_amount_usd), 0)).where(Sale.created_at >= seven_days_ago)
    )
    purchases_7d = db.scalar(
        select(func.coalesce(func.sum(Purchase.total_usd), 0)).where(Purchase.created_at >= seven_days_ago)
    )
    margin = float(sales_7d or 0) - float(purchases_7d or 0)

    setting = db.scalar(select(SystemSetting).where(SystemSetting.key == "operational_currency"))
    operational_currency = setting.value if setting else "USD"

    return {
        "range": "7d",
        "currency_code": operational_currency,
        "sales_usd": float(sales_7d or 0),
        "discounts_usd": float(discount_7d or 0),
        "purchases_usd": float(purchases_7d or 0),
        "gross_margin_usd": round(margin, 2),
    }


@router.get("/daily")
def daily_report(
    target_date: date | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("reports:view")),
) -> dict:
    day = target_date or datetime.now(timezone.utc).date()
    start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    end = start + timedelta(days=1)

    sales = db.scalar(
        select(func.coalesce(func.sum(Sale.total_usd), 0)).where(Sale.created_at >= start).where(Sale.created_at < end)
    )
    purchases = db.scalar(
        select(func.coalesce(func.sum(Purchase.total_usd), 0))
        .where(Purchase.created_at >= start)
        .where(Purchase.created_at < end)
    )

    return {
        "date": day.isoformat(),
        "sales_usd": float(sales or 0),
        "purchases_usd": float(purchases or 0),
    }
