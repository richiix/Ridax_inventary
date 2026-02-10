from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProductPriceHistory(Base):
    __tablename__ = "product_price_history"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    changed_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(String(180), default="")
    currency_code: Mapped[str] = mapped_column(String(10), nullable=False)
    old_cost_amount: Mapped[float] = mapped_column(Float, default=0)
    new_cost_amount: Mapped[float] = mapped_column(Float, default=0)
    old_base_price_amount: Mapped[float] = mapped_column(Float, default=0)
    new_base_price_amount: Mapped[float] = mapped_column(Float, default=0)
    old_base_discount_pct: Mapped[float] = mapped_column(Float, default=0)
    new_base_discount_pct: Mapped[float] = mapped_column(Float, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
