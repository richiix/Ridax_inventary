from pydantic import BaseModel


class InventoryAdjustRequest(BaseModel):
    product_id: int
    quantity: int
    adjust_type: str = "entry"
    note: str = ""
