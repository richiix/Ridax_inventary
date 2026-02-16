from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String
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
    seller_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    sale_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payment_currency_code: Mapped[str | None] = mapped_column(String(10), default="USD", nullable=True)
    payment_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    payment_rate_to_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    payment_amount_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    manual_total_override: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    manual_total_input_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    manual_total_original_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    manual_total_set_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    manual_total_set_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    commission_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    commission_amount_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    is_voided: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    voided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    void_reason: Mapped[str] = mapped_column(String(255), default="")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
