from pydantic import BaseModel


class SaleLineRequest(BaseModel):
    product_id: int
    quantity: int


class SaleCreateRequest(BaseModel):
    customer_name: str = ""
    customer_phone: str = ""
    customer_address: str = ""
    customer_rif: str = ""
    currency_code: str = "USD"
    discount_pct: float | None = None
    items: list[SaleLineRequest]
