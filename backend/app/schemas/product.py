from pydantic import BaseModel


class ProductCreate(BaseModel):
    name: str
    product_type: str = ""
    brand: str = ""
    model: str = ""
    measure_quantity: float = 1
    measure_unit: str = "unidad"
    description: str = ""
    invoice_note: str = ""
    cost_amount: float = 0
    base_price_amount: float
    final_customer_price: float
    wholesale_price: float = 0
    retail_price: float = 0
    currency_code: str = "USD"
    stock: int = 0
    is_active: bool = True


class ProductRead(BaseModel):
    id: int
    sku: str
    name: str
    product_type: str
    brand: str
    model: str
    measure_quantity: float
    measure_unit: str
    description: str
    invoice_note: str
    cost_amount: float
    base_price_amount: float
    final_customer_price: float
    wholesale_price: float
    retail_price: float
    currency_code: str
    stock: int
    is_active: bool


class ProductUpdate(BaseModel):
    name: str
    product_type: str = ""
    brand: str = ""
    model: str = ""
    measure_quantity: float = 1
    measure_unit: str = "unidad"
    description: str = ""
    invoice_note: str = ""
    cost_amount: float = 0
    base_price_amount: float
    final_customer_price: float
    wholesale_price: float = 0
    retail_price: float = 0
    currency_code: str = "USD"
    stock: int = 0
    is_active: bool = True
    change_reason: str = "Actualizacion manual"
