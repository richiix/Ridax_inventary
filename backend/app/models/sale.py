from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Sale(Base):
    __tablename__ = "sales"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    invoice_code: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    currency_code: Mapped[str] = mapped_column(String(10), default="USD", nullable=False)
    unit_price_usd: Mapped[float] = mapped_column(Float, nullable=False)
    subtotal_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    discount_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    discount_amount_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    tax_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    tax_amount_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    total_usd: Mapped[float] = mapped_column(Float, nullable=False)
    customer_name: Mapped[str] = mapped_column(String(140), default="")
    customer_phone: Mapped[str] = mapped_column(String(50), default="")
    customer_address: Mapped[str] = mapped_column(String(255), default="")
    customer_rif: Mapped[str] = mapped_column(String(60), default="")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
