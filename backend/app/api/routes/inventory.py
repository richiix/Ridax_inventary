from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import log_action, require_permission
from app.db.session import get_db
from app.models.inventory import InventoryMovement
from app.models.product import Product
from app.models.user import User
from app.schemas.inventory import InventoryAdjustRequest


router = APIRouter()


@router.get("")
def inventory_overview(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("inventory:view")),
) -> list[dict]:
    products = db.scalars(select(Product).order_by(Product.name.asc())).all()
    return [
        {
            "product_id": p.id,
            "sku": p.sku,
            "name": p.name,
            "stock": p.stock,
            "status": "BAJO" if p.stock <= 5 else "OK",
            "created_at": p.created_at.isoformat(),
        }
        for p in products
    ]


@router.post("/adjust")
def adjust_inventory(
    payload: InventoryAdjustRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory:write")),
) -> dict:
    product = db.scalar(select(Product).where(Product.id == payload.product_id))
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    if payload.quantity <= 0:
        raise HTTPException(status_code=400, detail="Cantidad debe ser mayor a cero")

    adjust_type = payload.adjust_type.lower()
    if adjust_type not in {"entry", "exit"}:
        raise HTTPException(status_code=400, detail="Tipo de ajuste invalido")

    signed_quantity = payload.quantity if adjust_type == "entry" else -payload.quantity
    if product.stock + signed_quantity < 0:
        raise HTTPException(status_code=400, detail="Stock insuficiente para salida")

    product.stock += signed_quantity
    movement = InventoryMovement(
        product_id=product.id,
        movement_type="adjustment_in" if adjust_type == "entry" else "adjustment_out",
        quantity=signed_quantity,
        note=payload.note,
        created_by=current_user.id,
    )
    db.add(movement)
    db.commit()
    db.refresh(movement)

    log_action(db, current_user.id, "adjust", "inventory", f"Producto {product.sku}: {signed_quantity}")
    return {
        "message": "Inventario actualizado",
        "new_stock": product.stock,
        "movement_type": movement.movement_type,
        "created_at": movement.created_at.isoformat(),
    }


@router.get("/movements")
def list_movements(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("inventory:view")),
) -> list[dict]:
    rows = db.scalars(select(InventoryMovement).order_by(InventoryMovement.id.desc()).limit(50)).all()
    return [
        {
            "id": row.id,
            "product_id": row.product_id,
            "movement_type": row.movement_type,
            "quantity": row.quantity,
            "note": row.note,
            "created_by": row.created_by,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]
