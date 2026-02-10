from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SkuSequence(Base):
    __tablename__ = "sku_sequences"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    sequence_key: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    last_value: Mapped[int] = mapped_column(default=0, nullable=False)
