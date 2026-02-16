from datetime import datetime

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
    seller_user_id: int | None = None
    sale_date: datetime | None = None
    payment_currency_code: str = "USD"
    payment_amount: float | None = None
    manual_invoice_total: float | None = None
    confirm_possible_duplicate: bool = False
    items: list[SaleLineRequest]


class InvoiceVoidRequest(BaseModel):
    invoice_codes: list[str]
    reason: str = ""


class InvoiceEditHeaderRequest(BaseModel):
    customer_name: str = ""
    customer_phone: str = ""
    customer_address: str = ""
    customer_rif: str = ""
    seller_user_id: int | None = None
    sale_date: datetime | None = None
    payment_currency_code: str = "USD"
    payment_amount: float | None = None
    manual_invoice_total: float | None = None


class InvoiceEditRequest(InvoiceEditHeaderRequest):
    items: list[SaleLineRequest] | None = None
