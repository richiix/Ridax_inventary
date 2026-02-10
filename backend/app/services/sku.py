from __future__ import annotations

import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.sku_sequence import SkuSequence


def _normalize_segment(value: str, fallback: str, max_len: int) -> str:
    raw = (value or "").strip()
    if not raw:
        return fallback

    ascii_text = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^A-Za-z0-9]", "", ascii_text).upper()
    if not cleaned:
        return fallback
    return cleaned[:max_len]


def build_sku_key(brand: str, product_type: str, measure: str) -> str:
    brand_part = _normalize_segment(brand, "GEN", 4)
    type_part = _normalize_segment(product_type, "GEN", 4)
    measure_part = _normalize_segment(measure, "NA", 6)
    return f"{brand_part}-{type_part}-{measure_part}"


def next_sku(db: Session, brand: str, product_type: str, measure: str) -> str:
    key = build_sku_key(brand, product_type, measure)

    for _ in range(3):
        try:
            sequence = db.scalar(select(SkuSequence).where(SkuSequence.sequence_key == key).with_for_update())
            if not sequence:
                sequence = SkuSequence(sequence_key=key, last_value=0)
                db.add(sequence)
                db.flush()

            sequence.last_value += 1
            db.flush()
            return f"RIDAX-{key}-{sequence.last_value:05d}"
        except IntegrityError:
            db.rollback()

    raise ValueError("No se pudo generar SKU unico")
