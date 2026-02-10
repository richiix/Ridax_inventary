from pydantic import BaseModel


class OperationalCurrencyUpdateRequest(BaseModel):
    currency_code: str


class CurrencyRateUpdateRequest(BaseModel):
    currency_code: str
    rate_to_usd: float


class ReceiptCompanySettingsRequest(BaseModel):
    company_name: str = "RIDAX"
    company_phone: str = ""
    company_address: str = ""
    company_rif: str = ""


class UserPreferencesUpdateRequest(BaseModel):
    preferred_language: str
    preferred_currency: str


class AdminUserPreferencesUpdateRequest(BaseModel):
    preferred_language: str
    preferred_currency: str
    telegram_chat_id: str = ""


class RolePermissionsUpdateRequest(BaseModel):
    permissions: list[str]


class GeneralSettingsUpdateRequest(BaseModel):
    modules_enabled_default: list[str]
    show_discount_in_invoice: bool
    sales_rounding_mode: str
    default_markup_percent: float
    invoice_tax_enabled: bool
    invoice_tax_percent: float
    ui_theme_mode: str
