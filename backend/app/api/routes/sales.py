from uuid import uuid4
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import log_action, require_permission
from app.db.session import get_db
from app.models.inventory import InventoryMovement
from app.models.currency import CurrencyRate
from app.models.product import Product
from app.models.sale import Sale
from app.models.system_setting import SystemSetting
from app.models.user import User
from app.schemas.sales import SaleCreateRequest


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


def build_invoice_payload(db: Session, invoice_code: str) -> dict:
    rows = db.scalars(select(Sale).where(Sale.invoice_code == invoice_code).order_by(Sale.id.asc())).all()
    if not rows:
        raise HTTPException(status_code=404, detail="Factura no encontrada")

    subtotal = round(sum(row.subtotal_usd for row in rows), 2)
    discount_amount = round(sum(row.discount_amount_usd for row in rows), 2)
    tax_amount = round(sum(row.tax_amount_usd for row in rows), 2)
    total = round(sum(row.total_usd for row in rows), 2)
    first = rows[0]
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
        "totals": {
            "subtotal": subtotal,
            "discount_pct": first.discount_pct,
            "discount_amount": discount_amount,
            "tax_pct": first.tax_pct,
            "tax_amount": tax_amount,
            "total": total,
            "show_discount": show_discount,
            "tax_enabled": tax_enabled,
        },
        "items": [
            {
                "sale_id": row.id,
                "product_id": row.product_id,
                "quantity": row.quantity,
                "unit_price": row.unit_price_usd,
                "subtotal": row.subtotal_usd,
                "discount_amount": row.discount_amount_usd,
                "tax_amount": row.tax_amount_usd,
                "total": row.total_usd,
            }
            for row in rows
        ],
    }


@router.get("")
def list_sales(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("sales:view")),
) -> list[dict]:
    rows = db.scalars(select(Sale).order_by(Sale.id.desc()).limit(100)).all()
    return [
        {
            "id": row.id,
            "invoice_code": row.invoice_code,
            "product_id": row.product_id,
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
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


@router.post("")
def create_sale(
    payload: SaleCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("sales:write")),
) -> dict:
    if not payload.items:
        raise HTTPException(status_code=400, detail="La factura debe tener al menos un articulo")

    currency = (payload.currency_code or "USD").upper()
    currency_exists = db.scalar(select(CurrencyRate).where(CurrencyRate.currency_code == currency))
    if not currency_exists:
        raise HTTPException(status_code=400, detail="Moneda invalida")

    product_ids = [line.product_id for line in payload.items]
    products = db.scalars(select(Product).where(Product.id.in_(product_ids))).all()
    products_map = {product.id: product for product in products}

    line_subtotals: list[tuple[Product, int, float]] = []
    invoice_subtotal = 0.0
    for line in payload.items:
        product = products_map.get(line.product_id)
        if not product:
            raise HTTPException(status_code=404, detail=f"Producto {line.product_id} no encontrado")
        if line.quantity <= 0:
            raise HTTPException(status_code=400, detail="Cantidad invalida")
        if product.stock < line.quantity:
            raise HTTPException(status_code=400, detail=f"Stock insuficiente para {product.sku}")

        line_subtotal = round(line.quantity * product.final_customer_price, 2)
        invoice_subtotal += line_subtotal
        line_subtotals.append((product, line.quantity, line_subtotal))

    invoice_subtotal = round(invoice_subtotal, 2)
    suggested_discount = 7.0 if invoice_subtotal > 300 else 0.0
    discount_pct = payload.discount_pct if payload.discount_pct is not None else suggested_discount
    discount_pct = max(0.0, discount_pct)
    invoice_discount_amount = round(invoice_subtotal * (discount_pct / 100), 2)
    taxable_base = round(invoice_subtotal - invoice_discount_amount, 2)
    tax_enabled = get_setting_bool(db, "invoice_tax_enabled", False)
    tax_pct = get_setting_float(db, "invoice_tax_percent", 16.0) if tax_enabled else 0.0
    invoice_tax_amount = round(taxable_base * (tax_pct / 100), 2)
    pre_round_total = round(taxable_base + invoice_tax_amount, 2)
    rounding_mode = get_setting_value(db, "sales_rounding_mode", "none")
    if rounding_mode == "nearest_integer":
        invoice_total = float(round(pre_round_total))
    else:
        invoice_total = pre_round_total
    invoice_code = f"FAC-{uuid4().hex[:10].upper()}"

    sale_rows: list[Sale] = []
    movement_rows: list[InventoryMovement] = []
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

        sale_rows.append(
            Sale(
                invoice_code=invoice_code,
                product_id=product.id,
                quantity=quantity,
                currency_code=currency,
                unit_price_usd=product.final_customer_price,
                subtotal_usd=line_subtotal,
                discount_pct=discount_pct,
                discount_amount_usd=line_discount,
                tax_pct=tax_pct,
                tax_amount_usd=line_tax,
                total_usd=line_total,
                customer_name=payload.customer_name,
                customer_phone=payload.customer_phone,
                customer_address=payload.customer_address,
                customer_rif=payload.customer_rif,
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
        "subtotal": invoice_subtotal,
        "discount_pct": discount_pct,
        "discount_amount": invoice_discount_amount,
        "tax_pct": tax_pct,
        "tax_amount": invoice_tax_amount,
        "sale_total": invoice_total,
        "line_count": len(sale_rows),
    }


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

    pdf.save()
    buffer.seek(0)
    filename = f"recibo-{invoice_code}.pdf"
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
