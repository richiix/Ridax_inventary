import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_permission
from app.core.config import get_settings
from app.db.session import get_db
from app.models.currency import CurrencyRate
from app.models.role import Role
from app.models.system_setting import SystemSetting
from app.models.user import User
from app.schemas.currency import CurrencyConvertRequest
from app.schemas.settings import (
    AdminUserPreferencesUpdateRequest,
    CurrencyRateUpdateRequest,
    GeneralSettingsUpdateRequest,
    OperationalCurrencyUpdateRequest,
    ReceiptCompanySettingsRequest,
    RolePermissionsUpdateRequest,
    UserPreferencesUpdateRequest,
)
from app.services.bcv import fetch_ves_rate_from_bcv
from app.services.currency import convert_amount
from app.services.rbac import available_permissions, parse_permissions


router = APIRouter()
settings = get_settings()


def get_setting_value(db: Session, key: str, default: str = "") -> str:
    row = db.scalar(select(SystemSetting).where(SystemSetting.key == key))
    return row.value if row else default


def set_setting_value(db: Session, key: str, value: str) -> None:
    row = db.scalar(select(SystemSetting).where(SystemSetting.key == key))
    if row:
        row.value = value
    else:
        db.add(SystemSetting(key=key, value=value))


def validate_preferences(db: Session, preferred_language: str, preferred_currency: str) -> tuple[str, str]:
    language = preferred_language.lower()
    if language not in {"es", "en"}:
        raise HTTPException(status_code=400, detail="Idioma no permitido")

    currency = preferred_currency.upper()
    exists = db.scalar(select(CurrencyRate).where(CurrencyRate.currency_code == currency))
    if not exists:
        raise HTTPException(status_code=400, detail="Moneda no registrada")

    return language, currency


def get_setting_bool(db: Session, key: str, default: bool) -> bool:
    raw = get_setting_value(db, key, "true" if default else "false").lower()
    return raw in {"true", "1", "yes"}


def get_setting_float(db: Session, key: str, default: float) -> float:
    raw = get_setting_value(db, key, str(default))
    try:
        return float(raw)
    except ValueError:
        return default


def get_setting_json_list(db: Session, key: str, default: list[str]) -> list[str]:
    raw = get_setting_value(db, key, json.dumps(default))
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else default
    except json.JSONDecodeError:
        return default


@router.get("/roles")
def roles(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("settings:view")),
) -> list[dict]:
    role_rows = db.scalars(select(Role).order_by(Role.id.asc())).all()
    return [
        {
            "id": row.id,
            "name": row.name,
            "permissions": parse_permissions(row.permissions),
        }
        for row in role_rows
    ]


@router.get("/permissions/catalog")
def permissions_catalog(_: User = Depends(require_permission("settings:view"))) -> dict:
    return {"permissions": available_permissions()}


@router.get("/general")
def general_settings(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    module_defaults = ["dashboard", "articles", "inventory", "sales", "purchases", "reports", "settings"]
    theme = get_setting_value(db, "ui_theme_mode", "dark")
    if theme not in {"dark", "light"}:
        theme = "dark"

    rounding = get_setting_value(db, "sales_rounding_mode", "none")
    if rounding not in {"none", "nearest_integer"}:
        rounding = "none"

    return {
        "modules_enabled_default": get_setting_json_list(db, "modules_enabled_default", module_defaults),
        "show_discount_in_invoice": get_setting_bool(db, "show_discount_in_invoice", True),
        "sales_rounding_mode": rounding,
        "default_markup_percent": get_setting_float(db, "default_markup_percent", 20.0),
        "invoice_tax_enabled": get_setting_bool(db, "invoice_tax_enabled", False),
        "invoice_tax_percent": get_setting_float(db, "invoice_tax_percent", 16.0),
        "ui_theme_mode": theme,
    }


@router.put("/general")
def save_general_settings(
    payload: GeneralSettingsUpdateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("settings:write")),
) -> dict:
    valid_modules = {"dashboard", "articles", "inventory", "sales", "purchases", "reports", "settings"}
    modules = [module for module in payload.modules_enabled_default if module in valid_modules]

    if payload.sales_rounding_mode not in {"none", "nearest_integer"}:
        raise HTTPException(status_code=400, detail="Modo de redondeo invalido")
    if payload.ui_theme_mode not in {"dark", "light"}:
        raise HTTPException(status_code=400, detail="Tema de interfaz invalido")
    if payload.invoice_tax_percent < 0:
        raise HTTPException(status_code=400, detail="IVA invalido")

    set_setting_value(db, "modules_enabled_default", json.dumps(modules))
    set_setting_value(db, "show_discount_in_invoice", "true" if payload.show_discount_in_invoice else "false")
    set_setting_value(db, "sales_rounding_mode", payload.sales_rounding_mode)
    set_setting_value(db, "default_markup_percent", str(payload.default_markup_percent))
    set_setting_value(db, "invoice_tax_enabled", "true" if payload.invoice_tax_enabled else "false")
    set_setting_value(db, "invoice_tax_percent", str(payload.invoice_tax_percent))
    set_setting_value(db, "ui_theme_mode", payload.ui_theme_mode)
    db.commit()

    return {"message": "Configuracion general actualizada"}


@router.put("/roles/{role_id}/permissions")
def update_role_permissions(
    role_id: int,
    payload: RolePermissionsUpdateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("settings:write")),
) -> dict:
    role = db.scalar(select(Role).where(Role.id == role_id))
    if not role:
        raise HTTPException(status_code=404, detail="Rol no encontrado")

    valid_permissions = set(available_permissions())
    clean_permissions = sorted({perm for perm in payload.permissions if perm in valid_permissions})
    role.permissions = json.dumps(clean_permissions)
    db.commit()
    return {
        "message": "Permisos actualizados",
        "role_id": role_id,
        "permissions": clean_permissions,
    }


@router.get("/languages")
def languages(_: User = Depends(require_permission("settings:view"))) -> dict:
    return {
        "default": settings.default_language,
        "enabled": ["es", "en"],
        "ready_for": ["pt", "fr"],
    }


@router.get("/preferences/options")
def preference_options(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    currency_rows = db.scalars(select(CurrencyRate).order_by(CurrencyRate.currency_code.asc())).all()
    return {
        "languages": ["es", "en"],
        "currencies": [row.currency_code for row in currency_rows],
        "preferred_language": current_user.preferred_language,
        "preferred_currency": current_user.preferred_currency,
    }


@router.get("/preferences/me")
def my_preferences(current_user: User = Depends(get_current_user)) -> dict:
    return {
        "preferred_language": current_user.preferred_language,
        "preferred_currency": current_user.preferred_currency,
    }


@router.get("/users/preferences")
def users_preferences(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("settings:view")),
) -> list[dict]:
    role_rows = db.scalars(select(Role)).all()
    role_map = {role.id: role.name for role in role_rows}
    user_rows = db.scalars(select(User).order_by(User.id.asc())).all()
    return [
        {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": role_map.get(user.role_id, "Sin rol"),
            "preferred_language": user.preferred_language,
            "preferred_currency": user.preferred_currency,
            "telegram_chat_id": user.telegram_chat_id,
            "is_active": user.is_active,
        }
        for user in user_rows
    ]


@router.put("/users/{user_id}/preferences")
def save_user_preferences_by_admin(
    user_id: int,
    payload: AdminUserPreferencesUpdateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("settings:write")),
) -> dict:
    user = db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    language, currency = validate_preferences(db, payload.preferred_language, payload.preferred_currency)
    user.preferred_language = language
    user.preferred_currency = currency
    user.telegram_chat_id = payload.telegram_chat_id.strip()
    db.commit()
    return {
        "message": "Preferencias del usuario actualizadas",
        "user_id": user.id,
        "preferred_language": language,
        "preferred_currency": currency,
        "telegram_chat_id": user.telegram_chat_id,
    }


@router.put("/preferences/me")
def save_my_preferences(
    payload: UserPreferencesUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    lang, currency = validate_preferences(db, payload.preferred_language, payload.preferred_currency)

    current_user.preferred_language = lang
    current_user.preferred_currency = currency
    db.commit()
    return {
        "message": "Preferencias actualizadas",
        "preferred_language": lang,
        "preferred_currency": currency,
    }


@router.get("/currencies")
def currencies(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("settings:view")),
) -> dict:
    operational_currency = get_setting_value(db, "operational_currency", settings.default_currency)
    rows = db.scalars(select(CurrencyRate).order_by(CurrencyRate.currency_code.asc())).all()
    return {
        "base_currency": settings.default_currency,
        "operational_currency": operational_currency,
        "rates": [
            {"currency_code": row.currency_code, "rate_to_usd": row.rate_to_usd, "updated_at": row.updated_at.isoformat()}
            for row in rows
        ],
    }


@router.put("/operational-currency")
def set_operational_currency(
    payload: OperationalCurrencyUpdateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("settings:write")),
) -> dict:
    code = payload.currency_code.upper()
    exists = db.scalar(select(CurrencyRate).where(CurrencyRate.currency_code == code))
    if not exists:
        raise HTTPException(status_code=400, detail="Moneda no registrada")

    set_setting_value(db, "operational_currency", code)
    db.commit()
    return {"message": "Moneda operativa actualizada", "operational_currency": code}


@router.get("/receipt-company")
def get_receipt_company_settings(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("settings:view")),
) -> dict:
    return {
        "company_name": get_setting_value(db, "receipt_company_name", "RIDAX"),
        "company_phone": get_setting_value(db, "receipt_company_phone", ""),
        "company_address": get_setting_value(db, "receipt_company_address", ""),
        "company_rif": get_setting_value(db, "receipt_company_rif", ""),
    }


@router.put("/receipt-company")
def save_receipt_company_settings(
    payload: ReceiptCompanySettingsRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("settings:write")),
) -> dict:
    set_setting_value(db, "receipt_company_name", payload.company_name)
    set_setting_value(db, "receipt_company_phone", payload.company_phone)
    set_setting_value(db, "receipt_company_address", payload.company_address)
    set_setting_value(db, "receipt_company_rif", payload.company_rif)
    db.commit()
    return {"message": "Datos de empresa para recibo actualizados"}


@router.post("/currencies/convert")
def currency_convert(
    payload: CurrencyConvertRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("settings:view")),
) -> dict:
    try:
        converted = convert_amount(db, payload.amount, payload.from_currency, payload.to_currency)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "amount": payload.amount,
        "from_currency": payload.from_currency.upper(),
        "to_currency": payload.to_currency.upper(),
        "converted_amount": converted,
    }


@router.put("/currencies/rate")
def update_currency_rate(
    payload: CurrencyRateUpdateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("settings:write")),
) -> dict:
    code = payload.currency_code.upper()
    rate = db.scalar(select(CurrencyRate).where(CurrencyRate.currency_code == code))
    if not rate:
        rate = CurrencyRate(currency_code=code, rate_to_usd=payload.rate_to_usd)
        db.add(rate)
    else:
        rate.rate_to_usd = payload.rate_to_usd
        rate.updated_at = datetime.now(timezone.utc)

    db.commit()
    return {"message": "Tasa actualizada", "currency_code": code, "rate_to_usd": payload.rate_to_usd}


@router.post("/currencies/update-ves-bcv")
async def update_ves_from_bcv(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("settings:write")),
) -> dict:
    try:
        rate_to_usd = await fetch_ves_rate_from_bcv()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"No se pudo obtener tasa BCV: {exc}") from exc

    ves = db.scalar(select(CurrencyRate).where(CurrencyRate.currency_code == "VES"))
    if not ves:
        ves = CurrencyRate(currency_code="VES", rate_to_usd=rate_to_usd)
        db.add(ves)
    else:
        ves.rate_to_usd = rate_to_usd
        ves.updated_at = datetime.now(timezone.utc)

    db.commit()
    return {
        "message": "Tasa VES actualizada desde BCV",
        "currency_code": "VES",
        "rate_to_usd": rate_to_usd,
        "source": "BCV",
    }
