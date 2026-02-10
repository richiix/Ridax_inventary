from pydantic import BaseModel


class PurchaseCreateRequest(BaseModel):
    product_id: int
    quantity: int
    unit_cost_usd: float
    supplier_name: str = ""
    purchase_note: str = ""
