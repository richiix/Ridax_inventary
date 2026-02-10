from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    sku: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    product_type: Mapped[str] = mapped_column(String(80), default="")
    brand: Mapped[str] = mapped_column(String(80), default="")
    model: Mapped[str] = mapped_column(String(80), default="")
    measure_quantity: Mapped[float] = mapped_column(Float, default=1.0)
    measure_unit: Mapped[str] = mapped_column(String(20), default="unidad")
    description: Mapped[str] = mapped_column(String(500), default="")
    invoice_note: Mapped[str] = mapped_column(String(255), default="")
    cost_amount: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    base_price_amount: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    base_discount_pct: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    final_customer_price: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    wholesale_price: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    retail_price: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    currency_code: Mapped[str] = mapped_column(String(10), default="USD", nullable=False)
    price_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    stock: Mapped[int] = mapped_column(default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
