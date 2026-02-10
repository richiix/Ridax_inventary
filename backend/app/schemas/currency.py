from pydantic import BaseModel


class CurrencyConvertRequest(BaseModel):
    amount: float
    from_currency: str
    to_currency: str
