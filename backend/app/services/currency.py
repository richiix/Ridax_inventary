from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.currency import CurrencyRate


def convert_amount(db: Session, amount: float, from_currency: str, to_currency: str) -> float:
    from_rate = db.scalar(
        select(CurrencyRate).where(CurrencyRate.currency_code == from_currency.upper())
    )
    to_rate = db.scalar(select(CurrencyRate).where(CurrencyRate.currency_code == to_currency.upper()))
    if not from_rate or not to_rate:
        raise ValueError("Moneda no registrada")

    amount_in_usd = amount / from_rate.rate_to_usd
    return round(amount_in_usd * to_rate.rate_to_usd, 2)
