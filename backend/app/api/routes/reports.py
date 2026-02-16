from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.product import Product
from app.models.purchase import Purchase
from app.models.sale import Sale
from app.models.system_setting import SystemSetting
from app.models.user import User


router = APIRouter()


def get_setting_value(db: Session, key: str, default: str = "") -> str:
    row = db.scalar(select(SystemSetting).where(SystemSetting.key == key))
    return row.value if row else default


def get_setting_float(db: Session, key: str, default: float) -> float:
    raw = get_setting_value(db, key, str(default))
    try:
        return float(raw)
    except ValueError:
        return default


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


def build_recommendations(lines: list[dict], purchases_total: float) -> list[str]:
    if not lines:
        return ["No hay ventas en el rango seleccionado."]

    recommendations: list[str] = []
    profits = [line["profit_line_usd"] for line in lines]
    low_margin = [line for line in lines if line["amount_paid_line_usd"] > 0 and (line["profit_line_usd"] / line["amount_paid_line_usd"]) < 0.1]
    discounted = [line for line in lines if line["discount_line_usd"] > 0]

    if low_margin:
        top_low = sorted(low_margin, key=lambda x: x["profit_line_usd"])[:3]
        names = ", ".join(f"{row['product_name']} ({row['invoice_code']})" for row in top_low)
        recommendations.append(f"Margen bajo detectado en: {names}. Revisa costo o precio de venta.")

    if discounted:
        total_discount = round(sum(line["discount_line_usd"] for line in discounted), 2)
        recommendations.append(f"Descuentos aplicados en el rango: USD {total_discount:.2f}. Evalua limites de oferta por producto.")

    best = max(lines, key=lambda x: x["profit_line_usd"])
    recommendations.append(
        f"Producto con mejor ganancia: {best['product_name']} ({best['invoice_code']}) con USD {best['profit_line_usd']:.2f}."
    )

    if purchases_total > 0 and sum(profits) < purchases_total * 0.1:
        recommendations.append("La utilidad es baja frente a compras; prioriza productos de mayor rotacion y margen.")

    return recommendations


@router.get("/kpis")
def kpis(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("reports:view")),
) -> dict:
    now = datetime.now(timezone.utc)
    seven_days_ago = now - timedelta(days=7)
    sales_7d = db.scalar(
        select(func.coalesce(func.sum(Sale.total_usd), 0))
        .where(Sale.created_at >= seven_days_ago)
        .where(Sale.is_voided.is_not(True))
    )
    discount_7d = db.scalar(
        select(func.coalesce(func.sum(Sale.discount_amount_usd), 0))
        .where(Sale.created_at >= seven_days_ago)
        .where(Sale.is_voided.is_not(True))
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
        select(func.coalesce(func.sum(Sale.total_usd), 0))
        .where(Sale.created_at >= start)
        .where(Sale.created_at < end)
        .where(Sale.is_voided.is_not(True))
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


@router.get("/range")
def range_report(
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("reports:view")),
) -> dict:
    range_from, range_to, start_dt, end_dt = resolve_range(from_date, to_date)
    commission_pct = get_setting_float(db, "sales_commission_pct", 7.0)

    sales_rows = db.execute(
        select(Sale, Product)
        .join(Product, Product.id == Sale.product_id)
        .where(Sale.is_voided.is_not(True))
        .where(func.coalesce(Sale.sale_date, Sale.created_at) >= start_dt)
        .where(func.coalesce(Sale.sale_date, Sale.created_at) < end_dt)
        .order_by(func.coalesce(Sale.sale_date, Sale.created_at).desc(), Sale.id.desc())
    ).all()

    purchase_rows = db.execute(
        select(Purchase, Product)
        .join(Product, Product.id == Purchase.product_id)
        .where(Purchase.created_at >= start_dt)
        .where(Purchase.created_at < end_dt)
        .order_by(Purchase.created_at.desc(), Purchase.id.desc())
    ).all()

    invoice_total_map: dict[str, float] = {}
    for sale_row, _product in sales_rows:
        invoice_total_map[sale_row.invoice_code] = round(invoice_total_map.get(sale_row.invoice_code, 0.0) + sale_row.total_usd, 2)

    sales_lines: list[dict] = []
    for sale_row, product in sales_rows:
        invoice_total = invoice_total_map.get(sale_row.invoice_code, 0.0)
        ratio = (sale_row.total_usd / invoice_total) if invoice_total > 0 else 0
        invoice_paid_usd = float(sale_row.payment_amount_usd or invoice_total)
        amount_paid_line_usd = round(invoice_paid_usd * ratio, 2)
        cost_line_usd = round((product.cost_amount or 0) * sale_row.quantity, 2)
        profit_line_usd = round(amount_paid_line_usd - cost_line_usd, 2)
        commission_line_usd = round(float(sale_row.commission_amount_usd or 0), 2)
        if commission_line_usd <= 0 and profit_line_usd > 0 and commission_pct > 0:
            commission_line_usd = round(profit_line_usd * (commission_pct / 100), 2)

        sales_lines.append(
            {
                "sale_id": sale_row.id,
                "invoice_code": sale_row.invoice_code,
                "sale_date": (sale_row.sale_date or sale_row.created_at).isoformat(),
                "product_id": product.id,
                "product_name": product.name,
                "product_type": product.product_type,
                "brand": product.brand,
                "model": product.model,
                "quantity": sale_row.quantity,
                "line_total_usd": round(sale_row.total_usd, 2),
                "discount_line_usd": round(sale_row.discount_amount_usd, 2),
                "amount_paid_line_usd": amount_paid_line_usd,
                "cost_line_usd": cost_line_usd,
                "profit_line_usd": profit_line_usd,
                "commission_pct": round(float(sale_row.commission_pct or commission_pct), 4),
                "commission_line_usd": commission_line_usd,
                "payment_currency_code": sale_row.payment_currency_code or "USD",
                "payment_amount_usd": round(invoice_paid_usd, 2),
            }
        )

    purchases = [
        {
            "id": purchase.id,
            "product_id": product.id,
            "product_name": product.name,
            "quantity": purchase.quantity,
            "unit_cost_usd": round(purchase.unit_cost_usd, 2),
            "total_usd": round(purchase.total_usd, 2),
            "supplier_name": purchase.supplier_name,
            "created_at": purchase.created_at.isoformat(),
        }
        for purchase, product in purchase_rows
    ]

    sales_total = round(sum(line["line_total_usd"] for line in sales_lines), 2)
    amount_paid_total = round(sum(line["amount_paid_line_usd"] for line in sales_lines), 2)
    cost_total = round(sum(line["cost_line_usd"] for line in sales_lines), 2)
    profit_total = round(sum(line["profit_line_usd"] for line in sales_lines), 2)
    commission_total = round(sum(line["commission_line_usd"] for line in sales_lines), 2)
    purchases_total = round(sum(row["total_usd"] for row in purchases), 2)
    margin_pct = round((profit_total / amount_paid_total) * 100, 2) if amount_paid_total > 0 else 0.0

    return {
        "range_from": range_from.isoformat(),
        "range_to": range_to.isoformat(),
        "summary": {
            "sales_usd": sales_total,
            "amount_paid_usd": amount_paid_total,
            "cost_of_sales_usd": cost_total,
            "gross_profit_usd": profit_total,
            "gross_margin_pct": margin_pct,
            "sales_commission_pct": commission_pct,
            "commission_total_usd": commission_total,
            "purchases_usd": purchases_total,
        },
        "sales_lines": sales_lines,
        "purchases": purchases,
        "recommendations": build_recommendations(sales_lines, purchases_total),
    }


@router.get("/commission-by-seller")
def commission_by_seller(
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("reports:view")),
) -> dict:
    range_from, range_to, start_dt, end_dt = resolve_range(from_date, to_date)
    commission_pct = get_setting_float(db, "sales_commission_pct", 7.0)

    sales_rows = db.scalars(
        select(Sale)
        .where(Sale.is_voided.is_not(True))
        .where(func.coalesce(Sale.sale_date, Sale.created_at) >= start_dt)
        .where(func.coalesce(Sale.sale_date, Sale.created_at) < end_dt)
        .order_by(func.coalesce(Sale.sale_date, Sale.created_at).desc(), Sale.id.desc())
    ).all()

    if not sales_rows:
        return {
            "range_from": range_from.isoformat(),
            "range_to": range_to.isoformat(),
            "commission_pct": commission_pct,
            "summary": {
                "amount_paid_usd": 0.0,
                "cost_usd": 0.0,
                "profit_usd": 0.0,
                "commission_usd": 0.0,
            },
            "sellers": [],
        }

    product_ids = {row.product_id for row in sales_rows}
    products = db.scalars(select(Product).where(Product.id.in_(product_ids))).all() if product_ids else []
    product_map = {product.id: product for product in products}

    invoice_total_map: dict[str, float] = {}
    invoice_paid_map: dict[str, float] = {}
    user_ids: set[int] = set()
    for row in sales_rows:
        invoice_total_map[row.invoice_code] = round(invoice_total_map.get(row.invoice_code, 0.0) + row.total_usd, 2)
        if row.payment_amount_usd is not None:
            invoice_paid_map[row.invoice_code] = float(row.payment_amount_usd)
        if row.seller_user_id:
            user_ids.add(row.seller_user_id)

    users = db.scalars(select(User).where(User.id.in_(user_ids))).all() if user_ids else []
    user_map = {user.id: (user.full_name or user.email) for user in users}

    seller_totals: dict[int, dict] = {}
    for row in sales_rows:
        seller_id = row.seller_user_id or 0
        seller_name = user_map.get(seller_id, "Sin vendedor")
        item = seller_totals.get(seller_id)
        if not item:
            item = {
                "seller_user_id": seller_id if seller_id else None,
                "seller_name": seller_name,
                "invoice_count": 0,
                "line_count": 0,
                "amount_paid_usd": 0.0,
                "cost_usd": 0.0,
                "profit_usd": 0.0,
                "commission_usd": 0.0,
            }
            seller_totals[seller_id] = item

        invoice_total = invoice_total_map.get(row.invoice_code, 0.0)
        ratio = (row.total_usd / invoice_total) if invoice_total > 0 else 0
        invoice_paid_usd = invoice_paid_map.get(row.invoice_code, invoice_total)
        amount_paid_line_usd = round(invoice_paid_usd * ratio, 2)
        unit_cost = float(product_map[row.product_id].cost_amount) if row.product_id in product_map else 0.0
        cost_line_usd = round(unit_cost * row.quantity, 2)
        profit_line_usd = round(amount_paid_line_usd - cost_line_usd, 2)
        commission_line_usd = round(float(row.commission_amount_usd or 0), 2)
        if commission_line_usd <= 0 and profit_line_usd > 0 and commission_pct > 0:
            commission_line_usd = round(profit_line_usd * (commission_pct / 100), 2)

        item["line_count"] += 1
        item["amount_paid_usd"] = round(item["amount_paid_usd"] + amount_paid_line_usd, 2)
        item["cost_usd"] = round(item["cost_usd"] + cost_line_usd, 2)
        item["profit_usd"] = round(item["profit_usd"] + profit_line_usd, 2)
        item["commission_usd"] = round(item["commission_usd"] + commission_line_usd, 2)

    counted_invoices: set[str] = set()
    for row in sales_rows:
        key = f"{row.seller_user_id or 0}:{row.invoice_code}"
        if key in counted_invoices:
            continue
        counted_invoices.add(key)
        seller_totals[row.seller_user_id or 0]["invoice_count"] += 1

    sellers = sorted(seller_totals.values(), key=lambda item: item["commission_usd"], reverse=True)
    summary = {
        "amount_paid_usd": round(sum(item["amount_paid_usd"] for item in sellers), 2),
        "cost_usd": round(sum(item["cost_usd"] for item in sellers), 2),
        "profit_usd": round(sum(item["profit_usd"] for item in sellers), 2),
        "commission_usd": round(sum(item["commission_usd"] for item in sellers), 2),
    }

    return {
        "range_from": range_from.isoformat(),
        "range_to": range_to.isoformat(),
        "commission_pct": commission_pct,
        "summary": summary,
        "sellers": sellers,
    }
