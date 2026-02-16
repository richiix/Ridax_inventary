import csv
from datetime import datetime, timedelta, timezone
from io import StringIO
from uuid import uuid4
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.api.deps import log_action, require_permission
from app.db.session import get_db
from app.models.inventory import InventoryMovement
from app.models.currency import CurrencyRate
from app.models.product import Product
from app.models.role import Role
from app.models.sale import Sale
from app.models.system_setting import SystemSetting
from app.models.user import User
from app.schemas.sales import InvoiceEditRequest, InvoiceVoidRequest, SaleCreateRequest


router = APIRouter()


def get_setting_value(db: Session, key: str, default: str = "") -> str:
    row = db.scalar(select(SystemSetting).where(SystemSetting.key == key))
    return row.value if row else default


def get_setting_bool(db: Session, key: str, default: bool) -> bool:
    raw = get_setting_value(db, key, "true" if default else "false").lower()
    return raw in {"true", "1", "yes"}


def get_setting_float(db: Session, key: str, default: float) -> float:
    raw = get_setting_value(db, key, str(default))
    try:
        return float(raw)
    except ValueError:
        return default


def can_assign_other_seller(db: Session, user: User) -> bool:
    role = db.scalar(select(Role).where(Role.id == user.role_id))
    if not role:
        return False
    return role.name.lower() in {"admin", "gerente"}


def is_admin_user(db: Session, user: User) -> bool:
    role = db.scalar(select(Role).where(Role.id == user.role_id))
    return bool(role and role.name.lower() == "admin")


def can_edit_invoice_header(row: Sale, current_user: User, is_admin: bool) -> bool:
    if is_admin:
        return True
    owner_id = row.seller_user_id or row.created_by
    return owner_id == current_user.id


def resolve_seller(
    db: Session,
    current_user: User,
    seller_user_id: int | None,
    allow_assign_other: bool,
) -> User:
    resolved_seller_id = seller_user_id or current_user.id
    if resolved_seller_id != current_user.id and not allow_assign_other:
        raise HTTPException(status_code=403, detail="No puedes asignar ventas a otro vendedor")

    seller = db.scalar(select(User).where(User.id == resolved_seller_id))
    if not seller or not seller.is_active:
        raise HTTPException(status_code=400, detail="Vendedor invalido")
    return seller


def resolve_payment(
    db: Session,
    payment_currency_code: str,
    payment_amount: float | None,
    invoice_total: float,
) -> tuple[str, float, float, float]:
    payment_currency = (payment_currency_code or "USD").upper()
    payment_rate = db.scalar(select(CurrencyRate).where(CurrencyRate.currency_code == payment_currency))
    if not payment_rate:
        raise HTTPException(status_code=400, detail="Moneda de pago invalida")

    resolved_payment_amount = payment_amount
    if resolved_payment_amount is None:
        resolved_payment_amount = round(invoice_total * payment_rate.rate_to_usd, 2)
    if resolved_payment_amount <= 0:
        raise HTTPException(status_code=400, detail="Monto pagado invalido")
    payment_amount_usd = round(resolved_payment_amount / payment_rate.rate_to_usd, 2)
    return payment_currency, resolved_payment_amount, payment_rate.rate_to_usd, payment_amount_usd


def build_invoice_lines(
    db: Session,
    items: list[tuple[Product, int]],
    discount_pct: float,
) -> dict:
    line_subtotals: list[tuple[Product, int, float]] = []
    invoice_subtotal = 0.0
    for product, quantity in items:
        if quantity <= 0:
            raise HTTPException(status_code=400, detail="Cantidad invalida")
        line_subtotal = round(quantity * product.final_customer_price, 2)
        invoice_subtotal += line_subtotal
        line_subtotals.append((product, quantity, line_subtotal))

    invoice_subtotal = round(invoice_subtotal, 2)
    discount_pct = max(0.0, discount_pct)
    invoice_discount_amount = round(invoice_subtotal * (discount_pct / 100), 2)
    taxable_base = round(invoice_subtotal - invoice_discount_amount, 2)
    tax_enabled = get_setting_bool(db, "invoice_tax_enabled", False)
    tax_pct = get_setting_float(db, "invoice_tax_percent", 16.0) if tax_enabled else 0.0
    invoice_tax_amount = round(taxable_base * (tax_pct / 100), 2)
    pre_round_total = round(taxable_base + invoice_tax_amount, 2)
    rounding_mode = get_setting_value(db, "sales_rounding_mode", "none")
    invoice_total = float(round(pre_round_total)) if rounding_mode == "nearest_integer" else pre_round_total

    lines: list[dict] = []
    distributed_discount = 0.0
    distributed_tax = 0.0
    distributed_total = 0.0
    for index, (product, quantity, line_subtotal) in enumerate(line_subtotals):
        if index == len(line_subtotals) - 1:
            line_discount = round(invoice_discount_amount - distributed_discount, 2)
            line_tax = round(invoice_tax_amount - distributed_tax, 2)
            line_total = round(invoice_total - distributed_total, 2)
        else:
            ratio = (line_subtotal / invoice_subtotal) if invoice_subtotal > 0 else 0
            line_discount = round(invoice_discount_amount * ratio, 2)
            distributed_discount += line_discount
            line_tax = round(invoice_tax_amount * ratio, 2)
            distributed_tax += line_tax
            line_total = round((line_subtotal - line_discount) + line_tax, 2)
            distributed_total += line_total

        lines.append(
            {
                "product": product,
                "quantity": quantity,
                "unit_price_usd": product.final_customer_price,
                "subtotal_usd": line_subtotal,
                "discount_amount_usd": line_discount,
                "tax_pct": tax_pct,
                "tax_amount_usd": line_tax,
                "total_usd": line_total,
            }
        )

    return {
        "discount_pct": discount_pct,
        "subtotal": invoice_subtotal,
        "discount_amount": invoice_discount_amount,
        "tax_pct": tax_pct,
        "tax_amount": invoice_tax_amount,
        "total": invoice_total,
        "lines": lines,
    }


def apply_manual_total_override(calc: dict, manual_invoice_total: float) -> tuple[dict, float]:
    manual_total = round(float(manual_invoice_total), 2)
    if manual_total <= 0:
        raise HTTPException(status_code=400, detail="El total manual debe ser mayor a cero")

    original_total = round(float(calc["total"]), 2)
    lines = calc["lines"]
    if not lines:
        raise HTTPException(status_code=400, detail="La factura debe tener al menos una linea")

    distributed_total = 0.0
    line_count = len(lines)
    base_sum = round(sum(float(line["total_usd"]) for line in lines), 2)
    for index, line in enumerate(lines):
        if index == line_count - 1:
            line_total = round(manual_total - distributed_total, 2)
        else:
            ratio = (float(line["total_usd"]) / base_sum) if base_sum > 0 else (1 / line_count)
            line_total = round(manual_total * ratio, 2)
            distributed_total += line_total
        line["total_usd"] = line_total

    calc["total"] = manual_total
    return calc, original_total


def calculate_commissions_for_lines(lines: list[dict], payment_amount_usd: float, commission_pct: float) -> tuple[list[dict], float]:
    payment_usd = round(float(payment_amount_usd or 0), 2)
    commission_rate = max(0.0, float(commission_pct)) / 100
    invoice_total = round(sum(float(line["total_usd"]) for line in lines), 2)

    enriched: list[dict] = []
    distributed_paid = 0.0
    for index, line in enumerate(lines):
        line_total = round(float(line["total_usd"]), 2)
        if index == len(lines) - 1:
            amount_paid_line = round(payment_usd - distributed_paid, 2)
        else:
            ratio = (line_total / invoice_total) if invoice_total > 0 else 0
            amount_paid_line = round(payment_usd * ratio, 2)
            distributed_paid += amount_paid_line

        product = line.get("product")
        quantity = int(line.get("quantity") or 0)
        unit_cost = float(product.cost_amount or 0) if product else 0.0
        cost_line = round(unit_cost * quantity, 2)
        profit_line = round(amount_paid_line - cost_line, 2)

        if index == len(lines) - 1:
            commission_line = round(max(0.0, profit_line) * commission_rate, 2)
            commission_line = round(max(0.0, commission_line), 2)
        else:
            commission_line = round(max(0.0, profit_line) * commission_rate, 2)

        enriched.append(
            {
                "amount_paid_line_usd": amount_paid_line,
                "cost_line_usd": cost_line,
                "profit_line_usd": profit_line,
                "commission_line_usd": commission_line,
            }
        )

    commission_total = round(sum(line["commission_line_usd"] for line in enriched), 2)
    return enriched, commission_total


def build_invoice_payload(db: Session, invoice_code: str) -> dict:
    rows = db.scalars(
        select(Sale)
        .where(Sale.invoice_code == invoice_code)
        .where(Sale.is_voided.is_not(True))
        .order_by(Sale.id.asc())
    ).all()
    if not rows:
        raise HTTPException(status_code=404, detail="Factura no encontrada")

    subtotal = round(sum(row.subtotal_usd for row in rows), 2)
    discount_amount = round(sum(row.discount_amount_usd for row in rows), 2)
    tax_amount = round(sum(row.tax_amount_usd for row in rows), 2)
    total = round(sum(row.total_usd for row in rows), 2)
    commission_total = round(sum(row.commission_amount_usd for row in rows), 2)
    first = rows[0]
    product_ids = {row.product_id for row in rows}
    product_rows = db.scalars(select(Product).where(Product.id.in_(product_ids))).all() if product_ids else []
    product_map = {product.id: product for product in product_rows}
    seller_name = ""
    if first.seller_user_id:
        seller = db.scalar(select(User).where(User.id == first.seller_user_id))
        if seller:
            seller_name = seller.full_name or seller.email
    show_discount = get_setting_bool(db, "show_discount_in_invoice", True)
    tax_enabled = get_setting_bool(db, "invoice_tax_enabled", False)

    return {
        "invoice_code": invoice_code,
        "created_at": first.created_at.isoformat(),
        "currency_code": first.currency_code,
        "company": {
            "name": get_setting_value(db, "receipt_company_name", "RIDAX"),
            "phone": get_setting_value(db, "receipt_company_phone", ""),
            "address": get_setting_value(db, "receipt_company_address", ""),
            "rif": get_setting_value(db, "receipt_company_rif", ""),
        },
        "customer": {
            "name": first.customer_name,
            "phone": first.customer_phone,
            "address": first.customer_address,
            "rif": first.customer_rif,
        },
        "sale": {
            "seller_user_id": first.seller_user_id,
            "seller_name": seller_name,
            "sale_date": (first.sale_date or first.created_at).isoformat(),
        },
        "totals": {
            "subtotal": subtotal,
            "discount_pct": first.discount_pct,
            "discount_amount": discount_amount,
            "tax_pct": first.tax_pct,
            "tax_amount": tax_amount,
            "commission_pct": first.commission_pct,
            "commission_amount": commission_total,
            "total": total,
            "show_discount": show_discount,
            "tax_enabled": tax_enabled,
        },
        "payment": {
            "currency_code": first.payment_currency_code or "USD",
            "amount": first.payment_amount,
            "rate_to_usd": first.payment_rate_to_usd,
            "amount_usd": first.payment_amount_usd,
            "difference_usd": round((first.payment_amount_usd or 0) - total, 2),
        },
        "manual_override": {
            "enabled": first.manual_total_override,
            "manual_total_input_usd": first.manual_total_input_usd,
            "manual_total_original_usd": first.manual_total_original_usd,
            "manual_total_set_by": first.manual_total_set_by,
            "manual_total_set_at": first.manual_total_set_at.isoformat() if first.manual_total_set_at else None,
        },
        "items": [
            {
                "sale_id": row.id,
                "product_id": row.product_id,
                "product_name": product_map[row.product_id].name if row.product_id in product_map else "",
                "brand": product_map[row.product_id].brand if row.product_id in product_map else "",
                "quantity": row.quantity,
                "unit_price": row.unit_price_usd,
                "subtotal": row.subtotal_usd,
                "discount_amount": row.discount_amount_usd,
                "tax_amount": row.tax_amount_usd,
                "total": row.total_usd,
                "commission_pct": row.commission_pct,
                "commission_amount_usd": row.commission_amount_usd,
            }
            for row in rows
        ],
    }


@router.get("")
def list_sales(
    only_voided: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("sales:view")),
) -> list[dict]:
    if only_voided and not is_admin_user(db, current_user):
        raise HTTPException(status_code=403, detail="Solo admin puede ver facturas anuladas")

    query = select(Sale).order_by(Sale.id.desc()).limit(200)
    if only_voided:
        query = query.where(Sale.is_voided.is_(True))
    else:
        query = query.where(Sale.is_voided.is_not(True))

    rows = db.scalars(query).all()
    product_ids = {row.product_id for row in rows}
    products = db.scalars(select(Product).where(Product.id.in_(product_ids))).all() if product_ids else []
    product_map = {product.id: product for product in products}
    user_ids = {row.seller_user_id for row in rows if row.seller_user_id}
    user_ids.update({row.voided_by for row in rows if row.voided_by})
    users = db.scalars(select(User).where(User.id.in_(user_ids))).all() if user_ids else []
    user_map = {user.id: (user.full_name or user.email) for user in users}
    payload: list[dict] = []
    for row in rows:
        product = product_map.get(row.product_id)
        payload.append(
            {
                "id": row.id,
                "invoice_code": row.invoice_code,
                "product_id": row.product_id,
                "product_name": product.name if product else "",
                "product_type": product.product_type if product else "",
                "brand": product.brand if product else "",
                "model": product.model if product else "",
                "quantity": row.quantity,
                "currency_code": row.currency_code,
                "unit_price_usd": row.unit_price_usd,
                "subtotal_usd": row.subtotal_usd,
                "discount_pct": row.discount_pct,
                "discount_amount_usd": row.discount_amount_usd,
                "tax_pct": row.tax_pct,
                "tax_amount_usd": row.tax_amount_usd,
                "total_usd": row.total_usd,
                "customer_name": row.customer_name,
                "customer_phone": row.customer_phone,
                "customer_address": row.customer_address,
                "customer_rif": row.customer_rif,
                "seller_user_id": row.seller_user_id,
                "seller_name": user_map.get(row.seller_user_id, ""),
                "sale_date": (row.sale_date or row.created_at).isoformat(),
                "payment_currency_code": row.payment_currency_code or "USD",
                "payment_amount": row.payment_amount,
                "payment_rate_to_usd": row.payment_rate_to_usd,
                "payment_amount_usd": row.payment_amount_usd,
                "commission_pct": row.commission_pct,
                "commission_amount_usd": row.commission_amount_usd,
                "manual_total_override": row.manual_total_override,
                "manual_total_input_usd": row.manual_total_input_usd,
                "manual_total_original_usd": row.manual_total_original_usd,
                "is_voided": row.is_voided,
                "voided_at": row.voided_at.isoformat() if row.voided_at else None,
                "voided_by": row.voided_by,
                "voided_by_name": user_map.get(row.voided_by, ""),
                "void_reason": row.void_reason,
                "created_at": row.created_at.isoformat(),
            }
        )
    return payload


@router.get("/products")
def sales_products(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("sales:view")),
) -> list[dict]:
    products = db.scalars(
        select(Product)
        .where(Product.is_active.is_(True))
        .where(Product.stock > 0)
        .order_by(Product.name.asc())
    ).all()
    return [
        {
            "id": item.id,
            "sku": item.sku,
            "name": item.name,
            "product_type": item.product_type,
            "brand": item.brand,
            "model": item.model,
            "final_customer_price": item.final_customer_price,
            "wholesale_price": item.wholesale_price,
            "retail_price": item.retail_price,
            "currency_code": item.currency_code,
            "stock": item.stock,
            "is_active": item.is_active,
        }
        for item in products
    ]


@router.get("/currencies")
def sales_currencies(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("sales:view")),
) -> list[dict]:
    rows = db.scalars(select(CurrencyRate).order_by(CurrencyRate.currency_code.asc())).all()
    return [
        {
            "currency_code": row.currency_code,
            "rate_to_usd": row.rate_to_usd,
        }
        for row in rows
    ]


@router.get("/vendors")
def sales_vendors(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("sales:view")),
) -> list[dict]:
    if can_assign_other_seller(db, current_user):
        users = db.scalars(select(User).where(User.is_active.is_(True)).order_by(User.full_name.asc())).all()
    else:
        users = [current_user]
    return [
        {
            "id": user.id,
            "full_name": user.full_name,
            "email": user.email,
        }
        for user in users
    ]


@router.post("")
def create_sale(
    payload: SaleCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("sales:write")),
) -> dict:
    if not payload.items:
        raise HTTPException(status_code=400, detail="La factura debe tener al menos un articulo")

    customer_name = payload.customer_name.strip()
    if not customer_name:
        raise HTTPException(status_code=400, detail="Debes indicar el nombre del cliente")

    admin_mode = is_admin_user(db, current_user)
    if payload.manual_invoice_total is not None and not admin_mode:
        raise HTTPException(status_code=403, detail="Solo admin puede definir total manual de factura")

    currency = (payload.currency_code or "USD").upper()
    currency_exists = db.scalar(select(CurrencyRate).where(CurrencyRate.currency_code == currency))
    if not currency_exists:
        raise HTTPException(status_code=400, detail="Moneda invalida")

    product_ids = [line.product_id for line in payload.items]
    products = db.scalars(select(Product).where(Product.id.in_(product_ids))).all()
    products_map = {product.id: product for product in products}
    validated_items: list[tuple[Product, int]] = []
    raw_subtotal = 0.0
    for line in payload.items:
        product = products_map.get(line.product_id)
        if not product:
            raise HTTPException(status_code=404, detail=f"Producto {line.product_id} no encontrado")
        if line.quantity <= 0:
            raise HTTPException(status_code=400, detail="Cantidad invalida")
        if product.stock < line.quantity:
            raise HTTPException(status_code=400, detail=f"Stock insuficiente para {product.sku}")

        validated_items.append((product, line.quantity))
        raw_subtotal += line.quantity * product.final_customer_price

    suggested_discount = 7.0 if raw_subtotal > 300 else 0.0
    discount_pct = payload.discount_pct if payload.discount_pct is not None else suggested_discount
    calc = build_invoice_lines(db, validated_items, discount_pct)
    manual_total_override = False
    manual_total_input_usd: float | None = None
    manual_total_original_usd: float | None = None
    manual_total_set_by: int | None = None
    manual_total_set_at: datetime | None = None
    if payload.manual_invoice_total is not None:
        calc, original_total = apply_manual_total_override(calc, payload.manual_invoice_total)
        manual_total_override = True
        manual_total_input_usd = round(float(payload.manual_invoice_total), 2)
        manual_total_original_usd = original_total
        manual_total_set_by = current_user.id
        manual_total_set_at = datetime.now(timezone.utc)

    invoice_subtotal = calc["subtotal"]
    invoice_discount_amount = calc["discount_amount"]
    tax_pct = calc["tax_pct"]
    invoice_tax_amount = calc["tax_amount"]
    invoice_total = calc["total"]

    duplicate_window_start = datetime.now(timezone.utc) - timedelta(hours=24)
    duplicate_rows = db.execute(
        select(
            Sale.invoice_code,
            func.max(func.coalesce(Sale.sale_date, Sale.created_at)).label("sale_date"),
            func.max(Sale.customer_name).label("customer_name"),
            func.sum(Sale.total_usd).label("invoice_total"),
        )
        .where(Sale.is_voided.is_not(True))
        .where(func.coalesce(Sale.sale_date, Sale.created_at) >= duplicate_window_start)
        .group_by(Sale.invoice_code)
        .having(func.abs(func.sum(Sale.total_usd) - invoice_total) <= 0.01)
        .order_by(func.max(func.coalesce(Sale.sale_date, Sale.created_at)).desc())
        .limit(8)
    ).all()
    if duplicate_rows and not payload.confirm_possible_duplicate:
        possible_duplicates = [
            {
                "invoice_code": row.invoice_code,
                "sale_date": row.sale_date.isoformat() if row.sale_date else None,
                "customer_name": row.customer_name,
                "invoice_total": round(float(row.invoice_total or 0), 2),
            }
            for row in duplicate_rows
        ]
        return JSONResponse(
            status_code=409,
            content={
                "detail": "Se detectaron facturas recientes con el mismo monto.",
                "possible_duplicates": possible_duplicates,
                "invoice_total": round(invoice_total, 2),
            },
        )

    seller = resolve_seller(db, current_user, payload.seller_user_id, allow_assign_other=can_assign_other_seller(db, current_user))
    seller_user_id = seller.id
    sale_date = payload.sale_date or datetime.now(timezone.utc)
    payment_currency, payment_amount, payment_rate_to_usd, payment_amount_usd = resolve_payment(
        db,
        payload.payment_currency_code,
        payload.payment_amount,
        invoice_total,
    )
    commission_pct = get_setting_float(db, "sales_commission_pct", 7.0)
    commission_lines, invoice_commission_total = calculate_commissions_for_lines(
        calc["lines"],
        payment_amount_usd,
        commission_pct,
    )

    invoice_code = f"FAC-{uuid4().hex[:10].upper()}"

    sale_rows: list[Sale] = []
    movement_rows: list[InventoryMovement] = []
    for line, line_financials in zip(calc["lines"], commission_lines):
        product = line["product"]
        quantity = line["quantity"]

        sale_rows.append(
            Sale(
                invoice_code=invoice_code,
                product_id=product.id,
                quantity=quantity,
                currency_code=currency,
                unit_price_usd=line["unit_price_usd"],
                subtotal_usd=line["subtotal_usd"],
                discount_pct=calc["discount_pct"],
                discount_amount_usd=line["discount_amount_usd"],
                tax_pct=line["tax_pct"],
                tax_amount_usd=line["tax_amount_usd"],
                total_usd=line["total_usd"],
                customer_name=customer_name,
                customer_phone=payload.customer_phone.strip(),
                customer_address=payload.customer_address.strip(),
                customer_rif=payload.customer_rif.strip(),
                seller_user_id=seller_user_id,
                sale_date=sale_date,
                payment_currency_code=payment_currency,
                payment_amount=payment_amount,
                payment_rate_to_usd=payment_rate_to_usd,
                payment_amount_usd=payment_amount_usd,
                manual_total_override=manual_total_override,
                manual_total_input_usd=manual_total_input_usd,
                manual_total_original_usd=manual_total_original_usd,
                manual_total_set_by=manual_total_set_by,
                manual_total_set_at=manual_total_set_at,
                commission_pct=commission_pct,
                commission_amount_usd=line_financials["commission_line_usd"],
                created_by=current_user.id,
            )
        )

        product.stock -= quantity
        movement_rows.append(
            InventoryMovement(
                product_id=product.id,
                movement_type="sale",
                quantity=-quantity,
                note=f"Venta {invoice_code} #{product.sku}",
                created_by=current_user.id,
            )
        )

    db.add_all([*sale_rows, *movement_rows])
    db.commit()

    log_action(db, current_user.id, "create", "sale", f"Factura {invoice_code} total {invoice_total}")
    return {
        "message": "Factura registrada",
        "invoice_code": invoice_code,
        "currency_code": currency,
        "seller_user_id": seller_user_id,
        "seller_name": seller.full_name,
        "sale_date": sale_date.isoformat(),
        "subtotal": invoice_subtotal,
        "discount_pct": discount_pct,
        "discount_amount": invoice_discount_amount,
        "tax_pct": tax_pct,
        "tax_amount": invoice_tax_amount,
        "payment_currency_code": payment_currency,
        "payment_amount": payment_amount,
        "payment_rate_to_usd": payment_rate_to_usd,
        "payment_amount_usd": payment_amount_usd,
        "payment_difference_usd": round(payment_amount_usd - invoice_total, 2),
        "commission_pct": commission_pct,
        "commission_amount_usd": invoice_commission_total,
        "manual_total_override": manual_total_override,
        "manual_total_input_usd": manual_total_input_usd,
        "manual_total_original_usd": manual_total_original_usd,
        "sale_total": invoice_total,
        "line_count": len(sale_rows),
    }


@router.post("/invoices/void")
def void_invoices(
    payload: InvoiceVoidRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("sales:write")),
) -> dict:
    if not is_admin_user(db, current_user):
        raise HTTPException(status_code=403, detail="Solo admin puede anular facturas")

    invoice_codes = [code.strip() for code in payload.invoice_codes if code and code.strip()]
    invoice_codes = list(dict.fromkeys(invoice_codes))
    if not invoice_codes:
        raise HTTPException(status_code=400, detail="Debes seleccionar al menos una factura")

    rows = db.scalars(
        select(Sale)
        .where(Sale.invoice_code.in_(invoice_codes))
        .where(Sale.is_voided.is_not(True))
        .order_by(Sale.id.asc())
    ).all()
    if not rows:
        raise HTTPException(status_code=404, detail="No se encontraron facturas activas para anular")

    products = db.scalars(select(Product).where(Product.id.in_({row.product_id for row in rows}))).all()
    product_map = {product.id: product for product in products}

    movements: list[InventoryMovement] = []
    now = datetime.now(timezone.utc)
    reason = payload.reason.strip() if payload.reason else ""

    for row in rows:
        product = product_map.get(row.product_id)
        if product:
            product.stock += row.quantity
            movement_note = f"Anulacion factura {row.invoice_code} #{product.sku}"
            if reason:
                movement_note = f"{movement_note} - {reason}"
            movements.append(
                InventoryMovement(
                    product_id=product.id,
                    movement_type="sale_reversal",
                    quantity=row.quantity,
                    note=movement_note,
                    created_by=current_user.id,
                )
            )

        row.is_voided = True
        row.voided_at = now
        row.voided_by = current_user.id
        row.void_reason = reason

    db.add_all(movements)
    db.commit()

    affected_invoices = sorted({row.invoice_code for row in rows})
    log_action(
        db,
        current_user.id,
        "void",
        "sale",
        f"Facturas anuladas ({len(affected_invoices)}): {', '.join(affected_invoices)}",
    )
    return {
        "message": "Facturas anuladas",
        "voided_invoices": affected_invoices,
        "voided_lines": len(rows),
    }


@router.patch("/invoice/{invoice_code}")
def edit_invoice(
    invoice_code: str,
    payload: InvoiceEditRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("sales:write")),
) -> dict:
    rows = db.scalars(
        select(Sale)
        .where(Sale.invoice_code == invoice_code)
        .where(Sale.is_voided.is_not(True))
        .order_by(Sale.id.asc())
    ).all()
    if not rows:
        raise HTTPException(status_code=404, detail="Factura no encontrada o anulada")

    first = rows[0]
    admin_mode = is_admin_user(db, current_user)
    if not can_edit_invoice_header(first, current_user, admin_mode):
        raise HTTPException(status_code=403, detail="No tienes permiso para editar esta factura")

    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No se enviaron cambios")

    if not admin_mode and "items" in updates:
        raise HTTPException(status_code=403, detail="Solo admin puede editar lineas de factura")
    if not admin_mode and "manual_invoice_total" in updates:
        raise HTTPException(status_code=403, detail="Solo admin puede definir total manual de factura")

    base_customer_name = str(updates.get("customer_name", first.customer_name)).strip()
    if not base_customer_name:
        raise HTTPException(status_code=400, detail="Debes indicar el nombre del cliente")
    base_customer_phone = str(updates.get("customer_phone", first.customer_phone))
    base_customer_address = str(updates.get("customer_address", first.customer_address))
    base_customer_rif = str(updates.get("customer_rif", first.customer_rif))

    seller = resolve_seller(
        db,
        current_user,
        updates.get("seller_user_id", first.seller_user_id or first.created_by),
        allow_assign_other=can_assign_other_seller(db, current_user),
    )
    sale_date = updates.get("sale_date", first.sale_date or first.created_at)

    movements: list[InventoryMovement] = []
    calc: dict
    manual_total_override = False
    manual_total_input_usd: float | None = None
    manual_total_original_usd: float | None = None
    manual_total_set_by: int | None = None
    manual_total_set_at: datetime | None = None

    replace_lines = admin_mode and ("items" in updates)
    if replace_lines:
        incoming_items = payload.items or []
        if not incoming_items:
            raise HTTPException(status_code=400, detail="La factura debe tener al menos un articulo")

        old_qty_by_product: dict[int, int] = {}
        for row in rows:
            old_qty_by_product[row.product_id] = old_qty_by_product.get(row.product_id, 0) + row.quantity

        new_qty_by_product: dict[int, int] = {}
        for item in incoming_items:
            if item.quantity <= 0:
                raise HTTPException(status_code=400, detail="Cantidad invalida")
            new_qty_by_product[item.product_id] = new_qty_by_product.get(item.product_id, 0) + item.quantity

        all_product_ids = set(old_qty_by_product) | set(new_qty_by_product)
        products = db.scalars(select(Product).where(Product.id.in_(all_product_ids))).all()
        products_map = {product.id: product for product in products}
        if len(products_map) != len(all_product_ids):
            raise HTTPException(status_code=404, detail="Uno o mas productos no existen")

        for product_id in all_product_ids:
            old_qty = old_qty_by_product.get(product_id, 0)
            new_qty = new_qty_by_product.get(product_id, 0)
            delta = new_qty - old_qty
            product = products_map[product_id]
            if delta > 0 and product.stock < delta:
                raise HTTPException(status_code=400, detail=f"Stock insuficiente para {product.sku}")

        for product_id in all_product_ids:
            old_qty = old_qty_by_product.get(product_id, 0)
            new_qty = new_qty_by_product.get(product_id, 0)
            delta = new_qty - old_qty
            product = products_map[product_id]
            if delta == 0:
                continue

            product.stock -= delta
            movements.append(
                InventoryMovement(
                    product_id=product.id,
                    movement_type="sale_edit_adjustment",
                    quantity=-delta,
                    note=f"Edicion factura {invoice_code} #{product.sku}",
                    created_by=current_user.id,
                )
            )

        line_items = [(products_map[product_id], qty) for product_id, qty in new_qty_by_product.items()]
        calc = build_invoice_lines(db, line_items, first.discount_pct)
    else:
        product_ids = {row.product_id for row in rows}
        product_rows = db.scalars(select(Product).where(Product.id.in_(product_ids))).all() if product_ids else []
        products_map = {product.id: product for product in product_rows}
        calc = {
            "discount_pct": first.discount_pct,
            "subtotal": round(sum(row.subtotal_usd for row in rows), 2),
            "discount_amount": round(sum(row.discount_amount_usd for row in rows), 2),
            "tax_pct": first.tax_pct,
            "tax_amount": round(sum(row.tax_amount_usd for row in rows), 2),
            "total": round(sum(row.total_usd for row in rows), 2),
            "lines": [
                {
                    "product": products_map.get(row.product_id),
                    "quantity": row.quantity,
                    "subtotal_usd": row.subtotal_usd,
                    "discount_amount_usd": row.discount_amount_usd,
                    "tax_pct": row.tax_pct,
                    "tax_amount_usd": row.tax_amount_usd,
                    "total_usd": row.total_usd,
                }
                for row in rows
            ],
        }

    requested_manual_total: float | None
    manual_from_existing = False
    if "manual_invoice_total" in updates:
        requested_manual_total = updates.get("manual_invoice_total")
    elif first.manual_total_override:
        requested_manual_total = first.manual_total_input_usd
        manual_from_existing = True
    else:
        requested_manual_total = None

    if requested_manual_total is not None:
        calc, original_total = apply_manual_total_override(calc, requested_manual_total)
        manual_total_override = True
        manual_total_input_usd = round(float(requested_manual_total), 2)
        manual_total_original_usd = original_total
        if manual_from_existing and "manual_invoice_total" not in updates:
            manual_total_set_by = first.manual_total_set_by
            manual_total_set_at = first.manual_total_set_at
        else:
            manual_total_set_by = current_user.id
            manual_total_set_at = datetime.now(timezone.utc)

    payment_currency, payment_amount, payment_rate_to_usd, payment_amount_usd = resolve_payment(
        db,
        str(updates.get("payment_currency_code", first.payment_currency_code or "USD")),
        updates.get("payment_amount", first.payment_amount),
        calc["total"],
    )
    commission_pct = get_setting_float(db, "sales_commission_pct", 7.0)
    commission_lines, invoice_commission_total = calculate_commissions_for_lines(
        calc["lines"],
        payment_amount_usd,
        commission_pct,
    )

    if replace_lines:
        created_at = first.created_at
        created_by = first.created_by
        db.execute(delete(Sale).where(Sale.invoice_code == invoice_code).where(Sale.is_voided.is_not(True)))
        db.flush()

        new_rows: list[Sale] = []
        for line, line_financials in zip(calc["lines"], commission_lines):
            product = line["product"]
            new_rows.append(
                Sale(
                    invoice_code=invoice_code,
                    product_id=product.id,
                    quantity=line["quantity"],
                    currency_code=first.currency_code,
                    unit_price_usd=line["unit_price_usd"],
                    subtotal_usd=line["subtotal_usd"],
                    discount_pct=calc["discount_pct"],
                    discount_amount_usd=line["discount_amount_usd"],
                    tax_pct=line["tax_pct"],
                    tax_amount_usd=line["tax_amount_usd"],
                    total_usd=line["total_usd"],
                    customer_name=base_customer_name,
                    customer_phone=base_customer_phone,
                    customer_address=base_customer_address,
                    customer_rif=base_customer_rif,
                    seller_user_id=seller.id,
                    sale_date=sale_date,
                    payment_currency_code=payment_currency,
                    payment_amount=payment_amount,
                    payment_rate_to_usd=payment_rate_to_usd,
                    payment_amount_usd=payment_amount_usd,
                    manual_total_override=manual_total_override,
                    manual_total_input_usd=manual_total_input_usd,
                    manual_total_original_usd=manual_total_original_usd,
                    manual_total_set_by=manual_total_set_by,
                    manual_total_set_at=manual_total_set_at,
                    commission_pct=commission_pct,
                    commission_amount_usd=line_financials["commission_line_usd"],
                    created_by=created_by,
                    created_at=created_at,
                )
            )
        db.add_all(new_rows)
    else:
        for row, line_financials in zip(rows, commission_lines):
            row.customer_name = base_customer_name
            row.customer_phone = base_customer_phone
            row.customer_address = base_customer_address
            row.customer_rif = base_customer_rif
            row.seller_user_id = seller.id
            row.sale_date = sale_date
            row.payment_currency_code = payment_currency
            row.payment_amount = payment_amount
            row.payment_rate_to_usd = payment_rate_to_usd
            row.payment_amount_usd = payment_amount_usd
            row.commission_pct = commission_pct
            row.commission_amount_usd = line_financials["commission_line_usd"]
            if "manual_invoice_total" in updates:
                row.manual_total_override = manual_total_override
                row.manual_total_input_usd = manual_total_input_usd
                row.manual_total_original_usd = manual_total_original_usd
                row.manual_total_set_by = manual_total_set_by
                row.manual_total_set_at = manual_total_set_at

    if movements:
        db.add_all(movements)

    db.commit()
    mode = "admin-line-edit" if replace_lines else "header-edit"
    log_action(db, current_user.id, "update", "sale", f"Factura {invoice_code} editada ({mode})")
    return {
        "message": "Factura actualizada",
        "invoice_code": invoice_code,
        "line_count": len(calc["lines"]),
        "subtotal": calc["subtotal"],
        "discount_pct": calc["discount_pct"],
        "discount_amount": calc["discount_amount"],
        "tax_pct": calc["tax_pct"],
        "tax_amount": calc["tax_amount"],
        "sale_total": calc["total"],
        "payment_currency_code": payment_currency,
        "payment_amount": payment_amount,
        "payment_amount_usd": payment_amount_usd,
        "payment_difference_usd": round(payment_amount_usd - calc["total"], 2),
        "commission_pct": commission_pct,
        "commission_amount_usd": invoice_commission_total,
        "manual_total_override": manual_total_override if "manual_invoice_total" in updates else first.manual_total_override,
        "manual_total_input_usd": manual_total_input_usd if "manual_invoice_total" in updates else first.manual_total_input_usd,
        "manual_total_original_usd": manual_total_original_usd if "manual_invoice_total" in updates else first.manual_total_original_usd,
        "edit_mode": mode,
    }


@router.get("/invoices/void/report")
def export_voided_invoices_report(
    format: str = Query(default="csv", pattern="^(csv|json)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("sales:view")),
):
    if not is_admin_user(db, current_user):
        raise HTTPException(status_code=403, detail="Solo admin puede exportar anulaciones")

    rows = db.scalars(
        select(Sale).where(Sale.is_voided.is_(True)).order_by(Sale.voided_at.desc(), Sale.invoice_code.asc())
    ).all()

    user_ids = {row.voided_by for row in rows if row.voided_by}
    user_ids.update({row.seller_user_id for row in rows if row.seller_user_id})
    users = db.scalars(select(User).where(User.id.in_(user_ids))).all() if user_ids else []
    user_map = {user.id: (user.full_name or user.email) for user in users}

    grouped: dict[str, dict] = {}
    for row in rows:
        key = row.invoice_code
        item = grouped.get(key)
        if not item:
            item = {
                "invoice_code": row.invoice_code,
                "sale_date": (row.sale_date or row.created_at).isoformat(),
                "voided_at": row.voided_at.isoformat() if row.voided_at else "",
                "voided_by": user_map.get(row.voided_by, ""),
                "void_reason": row.void_reason,
                "seller_name": user_map.get(row.seller_user_id, ""),
                "currency_code": row.currency_code,
                "line_count": 0,
                "quantity_total": 0,
                "subtotal_usd": 0.0,
                "discount_usd": 0.0,
                "tax_usd": 0.0,
                "total_usd": 0.0,
            }
            grouped[key] = item

        item["line_count"] += 1
        item["quantity_total"] += row.quantity
        item["subtotal_usd"] = round(item["subtotal_usd"] + row.subtotal_usd, 2)
        item["discount_usd"] = round(item["discount_usd"] + row.discount_amount_usd, 2)
        item["tax_usd"] = round(item["tax_usd"] + row.tax_amount_usd, 2)
        item["total_usd"] = round(item["total_usd"] + row.total_usd, 2)

    items = list(grouped.values())
    if format == "json":
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "count": len(items),
            "items": items,
        }

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "invoice_code",
            "sale_date",
            "voided_at",
            "voided_by",
            "void_reason",
            "seller_name",
            "currency_code",
            "line_count",
            "quantity_total",
            "subtotal_usd",
            "discount_usd",
            "tax_usd",
            "total_usd",
        ]
    )
    for item in items:
        writer.writerow(
            [
                item["invoice_code"],
                item["sale_date"],
                item["voided_at"],
                item["voided_by"],
                item["void_reason"],
                item["seller_name"],
                item["currency_code"],
                item["line_count"],
                item["quantity_total"],
                f"{item['subtotal_usd']:.2f}",
                f"{item['discount_usd']:.2f}",
                f"{item['tax_usd']:.2f}",
                f"{item['total_usd']:.2f}",
            ]
        )

    content = output.getvalue()
    output.close()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return StreamingResponse(
        iter([content]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="ridax-anulaciones-{stamp}.csv"'},
    )


@router.get("/invoice/{invoice_code}")
def get_invoice_detail(
    invoice_code: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("sales:view")),
) -> dict:
    return build_invoice_payload(db, invoice_code)


@router.get("/invoice/{invoice_code}/pdf")
def download_invoice_pdf(
    invoice_code: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("sales:view")),
) -> StreamingResponse:
    payload = build_invoice_payload(db, invoice_code)

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    y = height - 50
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(50, y, "RECIBO")
    y -= 24

    pdf.setFont("Helvetica", 10)
    pdf.drawString(50, y, f"Factura: {payload['invoice_code']}")
    pdf.drawString(280, y, f"Fecha: {payload['created_at']}")
    y -= 20

    company = payload["company"]
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(50, y, company["name"])
    y -= 14
    pdf.setFont("Helvetica", 10)
    pdf.drawString(50, y, f"Telefono: {company['phone']}")
    y -= 14
    pdf.drawString(50, y, f"Direccion: {company['address']}")
    y -= 14
    pdf.drawString(50, y, f"RIF: {company['rif']}")
    y -= 20

    customer = payload["customer"]
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(50, y, "Cliente")
    y -= 14
    pdf.setFont("Helvetica", 10)
    pdf.drawString(50, y, f"Nombre: {customer['name']}")
    y -= 14
    pdf.drawString(50, y, f"Telefono: {customer['phone']}")
    y -= 14
    pdf.drawString(50, y, f"Direccion: {customer['address']}")
    y -= 14
    pdf.drawString(50, y, f"RIF: {customer['rif']}")
    y -= 24

    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(50, y, "Producto ID")
    pdf.drawString(150, y, "Cant")
    pdf.drawString(210, y, "Precio")
    pdf.drawString(280, y, "Subtotal")
    pdf.drawString(360, y, "Desc")
    pdf.drawString(420, y, "IVA")
    pdf.drawString(470, y, "Total")
    y -= 12
    pdf.line(50, y, 540, y)
    y -= 14

    pdf.setFont("Helvetica", 10)
    for item in payload["items"]:
        if y < 90:
            pdf.showPage()
            y = height - 50
        pdf.drawString(50, y, str(item["product_id"]))
        pdf.drawString(150, y, str(item["quantity"]))
        pdf.drawString(210, y, f"{item['unit_price']:.2f}")
        pdf.drawString(280, y, f"{item['subtotal']:.2f}")
        pdf.drawString(360, y, f"{item['discount_amount']:.2f}")
        pdf.drawString(420, y, f"{item['tax_amount']:.2f}")
        pdf.drawString(470, y, f"{item['total']:.2f}")
        y -= 14

    y -= 10
    totals = payload["totals"]
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(320, y, f"Subtotal: {totals['subtotal']:.2f}")
    if totals["show_discount"]:
        y -= 14
        pdf.drawString(320, y, f"Descuento ({totals['discount_pct']:.2f}%): {totals['discount_amount']:.2f}")
    if totals["tax_enabled"]:
        y -= 14
        pdf.drawString(320, y, f"IVA ({totals['tax_pct']:.2f}%): {totals['tax_amount']:.2f}")
    y -= 14
    pdf.drawString(320, y, f"Total: {totals['total']:.2f} {payload['currency_code']}")

    payment = payload.get("payment") or {}
    if payment.get("amount") is not None:
        y -= 14
        pdf.drawString(320, y, f"Pago: {payment['amount']:.2f} {payment.get('currency_code', 'USD')}")
    if payment.get("rate_to_usd") is not None:
        y -= 14
        pdf.drawString(320, y, f"Tasa pago->USD: {payment['rate_to_usd']:.4f}")
    if payment.get("difference_usd") is not None:
        y -= 14
        pdf.drawString(320, y, f"Diferencia USD: {payment['difference_usd']:.2f}")

    pdf.save()
    buffer.seek(0)
    filename = f"recibo-{invoice_code}.pdf"
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
