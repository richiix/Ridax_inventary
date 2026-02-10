from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.product import Product


router = APIRouter()


@router.get("/catalog")
def catalog(db: Session = Depends(get_db)) -> dict:
    products = db.scalars(
        select(Product).where(Product.is_active.is_(True)).order_by(Product.id.desc())
    ).all()
    return {
        "channel": "ecommerce-ready",
        "items": [
            {
                "sku": p.sku,
                "name": p.name,
                "type": p.product_type,
                "brand": p.brand,
                "model": p.model,
                "measure": f"{p.measure_quantity} {p.measure_unit}",
                "description": p.description,
                "final_customer_price": p.final_customer_price,
                "retail_price": p.retail_price,
                "wholesale_price": p.wholesale_price,
                "currency_code": p.currency_code,
                "stock": p.stock,
            }
            for p in products
        ],
    }


@router.get("/health")
def public_health() -> dict:
    return {"status": "ok", "service": "RIDAX API"}
