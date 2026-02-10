from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import log_action, require_permission
from app.db.session import get_db
from app.models.inventory import InventoryMovement
from app.models.product import Product
from app.models.purchase import Purchase
from app.models.user import User
from app.schemas.purchases import PurchaseCreateRequest


router = APIRouter()


@router.get("")
def list_purchases(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("purchases:view")),
) -> list[dict]:
    rows = db.scalars(select(Purchase).order_by(Purchase.id.desc()).limit(100)).all()
    return [
        {
            "id": row.id,
            "product_id": row.product_id,
            "quantity": row.quantity,
            "unit_cost_usd": row.unit_cost_usd,
            "total_usd": row.total_usd,
            "supplier_name": row.supplier_name,
            "purchase_note": row.purchase_note,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


@router.post("")
def create_purchase(
    payload: PurchaseCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("purchases:write")),
) -> dict:
    product = db.scalar(select(Product).where(Product.id == payload.product_id))
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    if payload.quantity <= 0:
        raise HTTPException(status_code=400, detail="Cantidad invalida")

    total = round(payload.quantity * payload.unit_cost_usd, 2)
    purchase = Purchase(
        product_id=product.id,
        quantity=payload.quantity,
        unit_cost_usd=payload.unit_cost_usd,
        total_usd=total,
        supplier_name=payload.supplier_name,
        purchase_note=payload.purchase_note,
        created_by=current_user.id,
    )
    product.stock += payload.quantity
    movement = InventoryMovement(
        product_id=product.id,
        movement_type="purchase",
        quantity=payload.quantity,
        note=f"Compra #{product.sku}",
        created_by=current_user.id,
    )

    db.add_all([purchase, movement])
    db.commit()
    log_action(db, current_user.id, "create", "purchase", f"Compra total {total}")
    return {"message": "Compra registrada", "purchase_total_usd": total}
