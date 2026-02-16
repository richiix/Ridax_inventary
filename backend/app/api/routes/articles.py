from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, log_action, require_permission
from app.db.session import get_db
from app.models.product_price_history import ProductPriceHistory
from app.models.product import Product
from app.models.user import User
from app.schemas.product import ProductCreate, ProductUpdate
from app.services.sku import next_sku


router = APIRouter()


def build_measure_label(quantity: float, unit: str) -> str:
    normalized_qty = int(quantity) if float(quantity).is_integer() else quantity
    return f"{normalized_qty}{unit}"


@router.get("")
def list_articles(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("articles:view")),
) -> list[dict]:
    rows = db.scalars(
        select(Product).where(Product.is_active.is_(True)).order_by(Product.id.desc())
    ).all()
    return [
        {
            "id": row.id,
            "sku": row.sku,
            "name": row.name,
            "product_type": row.product_type,
            "brand": row.brand,
            "model": row.model,
            "measure_quantity": row.measure_quantity,
            "measure_unit": row.measure_unit,
            "description": row.description,
            "invoice_note": row.invoice_note,
            "cost_amount": row.cost_amount,
            "base_price_amount": row.base_price_amount,
            "final_customer_price": row.final_customer_price,
            "wholesale_price": row.wholesale_price,
            "retail_price": row.retail_price,
            "currency_code": row.currency_code,
            "price_usd": row.price_usd,
            "stock": row.stock,
            "is_active": row.is_active,
        }
        for row in rows
    ]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_article(
    payload: ProductCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("articles:write")),
) -> dict:
    measure_label = build_measure_label(payload.measure_quantity, payload.measure_unit)
    try:
        sku = next_sku(db, payload.brand, payload.product_type, measure_label)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    product = Product(
        sku=sku,
        name=payload.name,
        product_type=payload.product_type,
        brand=payload.brand,
        model=payload.model,
        measure_quantity=payload.measure_quantity,
        measure_unit=payload.measure_unit,
        description=payload.description,
        invoice_note=payload.invoice_note,
        cost_amount=payload.cost_amount,
        base_price_amount=payload.base_price_amount,
        final_customer_price=payload.final_customer_price,
        wholesale_price=payload.wholesale_price,
        retail_price=payload.retail_price,
        currency_code=payload.currency_code.upper(),
        price_usd=payload.final_customer_price,
        stock=payload.stock,
        is_active=payload.is_active,
    )
    db.add(product)
    db.commit()
    db.refresh(product)

    log_action(db, current_user.id, "create", "article", f"SKU {product.sku}")
    return {"id": product.id, "sku": product.sku, "message": "Articulo creado"}


@router.put("/{product_id}")
def update_article(
    product_id: int,
    payload: ProductUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("articles:write")),
) -> dict:
    product = db.scalar(select(Product).where(Product.id == product_id))
    if not product:
        raise HTTPException(status_code=404, detail="Articulo no encontrado")

    old_cost = product.cost_amount
    old_base = product.base_price_amount
    old_discount = product.base_discount_pct

    product.name = payload.name
    product.product_type = payload.product_type
    product.brand = payload.brand
    product.model = payload.model
    product.measure_quantity = payload.measure_quantity
    product.measure_unit = payload.measure_unit
    product.description = payload.description
    product.invoice_note = payload.invoice_note
    product.cost_amount = payload.cost_amount
    product.base_price_amount = payload.base_price_amount
    product.final_customer_price = payload.final_customer_price
    product.wholesale_price = payload.wholesale_price
    product.retail_price = payload.retail_price
    product.currency_code = payload.currency_code.upper()
    product.price_usd = payload.final_customer_price
    product.stock = payload.stock
    product.is_active = payload.is_active

    db.add(
        ProductPriceHistory(
            product_id=product.id,
            changed_by=current_user.id,
            reason=payload.change_reason,
            currency_code=product.currency_code,
            old_cost_amount=old_cost,
            new_cost_amount=product.cost_amount,
            old_base_price_amount=old_base,
            new_base_price_amount=product.base_price_amount,
            old_base_discount_pct=old_discount,
            new_base_discount_pct=product.base_discount_pct,
        )
    )
    db.commit()
    log_action(db, current_user.id, "update", "article", f"Articulo {product.sku} actualizado")
    return {"message": "Articulo actualizado"}


@router.patch("/{product_id}/visibility")
def set_article_visibility(
    product_id: int,
    visible: bool,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("articles:write")),
) -> dict:
    product = db.scalar(select(Product).where(Product.id == product_id))
    if not product:
        raise HTTPException(status_code=404, detail="Articulo no encontrado")

    product.is_active = visible
    db.commit()
    status_label = "visible" if visible else "oculto"
    log_action(db, current_user.id, "visibility", "article", f"Articulo {product.sku} -> {status_label}")
    return {"message": "Visibilidad actualizada", "is_active": product.is_active}


@router.delete("/{product_id}")
def logical_delete_article(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("articles:write")),
) -> dict:
    product = db.scalar(select(Product).where(Product.id == product_id))
    if not product:
        raise HTTPException(status_code=404, detail="Articulo no encontrado")

    product.is_active = False
    db.commit()
    log_action(db, current_user.id, "delete", "article", f"Articulo {product.sku} borrado logico")
    return {"message": "Articulo borrado logicamente", "is_active": product.is_active}


@router.get("/{product_id}/price-history")
def article_price_history(
    product_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("articles:view")),
) -> list[dict]:
    rows = db.scalars(
        select(ProductPriceHistory)
        .where(ProductPriceHistory.product_id == product_id)
        .order_by(ProductPriceHistory.id.desc())
        .limit(50)
    ).all()
    return [
        {
            "id": row.id,
            "reason": row.reason,
            "currency_code": row.currency_code,
            "old_cost_amount": row.old_cost_amount,
            "new_cost_amount": row.new_cost_amount,
            "old_base_price_amount": row.old_base_price_amount,
            "new_base_price_amount": row.new_base_price_amount,
            "old_base_discount_pct": row.old_base_discount_pct,
            "new_base_discount_pct": row.new_base_discount_pct,
            "changed_by": row.changed_by,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


@router.get("/{sku}")
def get_article(
    sku: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    product = db.scalar(select(Product).where(Product.sku == sku))
    if not product:
        raise HTTPException(status_code=404, detail="Articulo no encontrado")
    return {
        "id": product.id,
        "sku": product.sku,
        "name": product.name,
        "product_type": product.product_type,
        "brand": product.brand,
        "model": product.model,
        "measure_quantity": product.measure_quantity,
        "measure_unit": product.measure_unit,
        "description": product.description,
        "invoice_note": product.invoice_note,
        "cost_amount": product.cost_amount,
        "base_price_amount": product.base_price_amount,
        "final_customer_price": product.final_customer_price,
        "wholesale_price": product.wholesale_price,
        "retail_price": product.retail_price,
        "currency_code": product.currency_code,
        "price_usd": product.price_usd,
        "stock": product.stock,
        "is_active": product.is_active,
    }
