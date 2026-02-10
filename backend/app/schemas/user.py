from pydantic import BaseModel


class UserRead(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    permissions: list[str] = []
    preferred_language: str = "es"
    preferred_currency: str = "USD"
