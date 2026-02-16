import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_permission
from app.core.config import get_settings
from app.db.session import get_db
from app.models.currency import CurrencyRate
from app.models.inventory import InventoryMovement
from app.models.product import Product
from app.models.product_price_history import ProductPriceHistory
from app.models.purchase import Purchase
from app.models.role import Role
from app.models.sale import Sale
from app.models.sku_sequence import SkuSequence
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


def ensure_admin_user(db: Session, user: User) -> None:
    role = db.scalar(select(Role).where(Role.id == user.role_id))
    if not role or role.name.lower() != "admin":
        raise HTTPException(status_code=403, detail="Solo admin puede usar esta accion")


def parse_iso_datetime(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(timezone.utc)


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
        "sales_commission_pct": get_setting_float(db, "sales_commission_pct", 7.0),
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
    if payload.sales_commission_pct < 0:
        raise HTTPException(status_code=400, detail="Comision de ventas invalida")

    set_setting_value(db, "modules_enabled_default", json.dumps(modules))
    set_setting_value(db, "show_discount_in_invoice", "true" if payload.show_discount_in_invoice else "false")
    set_setting_value(db, "sales_rounding_mode", payload.sales_rounding_mode)
    set_setting_value(db, "default_markup_percent", str(payload.default_markup_percent))
    set_setting_value(db, "sales_commission_pct", str(payload.sales_commission_pct))
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


@router.get("/security/backup")
def export_security_backup(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("settings:view")),
) -> dict:
    ensure_admin_user(db, current_user)

    sales_rows = db.scalars(select(Sale).order_by(Sale.id.asc())).all()
    purchase_rows = db.scalars(select(Purchase).order_by(Purchase.id.asc())).all()
    movement_rows = db.scalars(select(InventoryMovement).order_by(InventoryMovement.id.asc())).all()
    product_rows = db.scalars(select(Product).order_by(Product.id.asc())).all()
    currency_rows = db.scalars(select(CurrencyRate).order_by(CurrencyRate.currency_code.asc())).all()
    setting_rows = db.scalars(select(SystemSetting).order_by(SystemSetting.key.asc())).all()
    sku_rows = db.scalars(select(SkuSequence).order_by(SkuSequence.sequence_key.asc())).all()
    price_history_rows = db.scalars(select(ProductPriceHistory).order_by(ProductPriceHistory.id.asc())).all()

    return {
        "format": "ridax-backup-v2",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "exported_by": current_user.email,
        "counts": {
            "sales": len(sales_rows),
            "purchases": len(purchase_rows),
            "inventory_snapshot": len(product_rows),
            "inventory_movements": len(movement_rows),
            "currency_rates": len(currency_rows),
            "system_settings": len(setting_rows),
            "sku_sequences": len(sku_rows),
            "product_price_history": len(price_history_rows),
        },
        "sales": [
            {
                "id": row.id,
                "invoice_code": row.invoice_code,
                "product_id": row.product_id,
                "quantity": row.quantity,
                "currency_code": row.currency_code,
                "unit_price_usd": row.unit_price_usd,
                "subtotal_usd": row.subtotal_usd,
                "discount_pct": row.discount_pct,
                "discount_amount_usd": row.discount_amount_usd,
                "tax_pct": row.tax_pct,
                "tax_amount_usd": row.tax_amount_usd,
                "total_usd": row.total_usd,
                "customer_name": row.customer_name,
                "customer_phone": row.customer_phone,
                "customer_address": row.customer_address,
                "customer_rif": row.customer_rif,
                "seller_user_id": row.seller_user_id,
                "sale_date": row.sale_date.isoformat() if row.sale_date else None,
                "payment_currency_code": row.payment_currency_code,
                "payment_amount": row.payment_amount,
                "payment_rate_to_usd": row.payment_rate_to_usd,
                "payment_amount_usd": row.payment_amount_usd,
                "manual_total_override": row.manual_total_override,
                "manual_total_input_usd": row.manual_total_input_usd,
                "manual_total_original_usd": row.manual_total_original_usd,
                "manual_total_set_by": row.manual_total_set_by,
                "manual_total_set_at": row.manual_total_set_at.isoformat() if row.manual_total_set_at else None,
                "commission_pct": row.commission_pct,
                "commission_amount_usd": row.commission_amount_usd,
                "is_voided": row.is_voided,
                "voided_at": row.voided_at.isoformat() if row.voided_at else None,
                "voided_by": row.voided_by,
                "void_reason": row.void_reason,
                "created_by": row.created_by,
                "created_at": row.created_at.isoformat(),
            }
            for row in sales_rows
        ],
        "purchases": [
            {
                "id": row.id,
                "product_id": row.product_id,
                "quantity": row.quantity,
                "unit_cost_usd": row.unit_cost_usd,
                "total_usd": row.total_usd,
                "supplier_name": row.supplier_name,
                "purchase_note": row.purchase_note,
                "created_by": row.created_by,
                "created_at": row.created_at.isoformat(),
            }
            for row in purchase_rows
        ],
        "inventory_snapshot": [
            {
                "product_id": row.id,
                "sku": row.sku,
                "name": row.name,
                "product_type": row.product_type,
                "brand": row.brand,
                "model": row.model,
                "currency_code": row.currency_code,
                "final_customer_price": row.final_customer_price,
                "wholesale_price": row.wholesale_price,
                "retail_price": row.retail_price,
                "stock": row.stock,
                "is_active": row.is_active,
                "created_at": row.created_at.isoformat(),
            }
            for row in product_rows
        ],
        "inventory_movements": [
            {
                "id": row.id,
                "product_id": row.product_id,
                "movement_type": row.movement_type,
                "quantity": row.quantity,
                "note": row.note,
                "created_by": row.created_by,
                "created_at": row.created_at.isoformat(),
            }
            for row in movement_rows
        ],
        "currency_rates": [
            {
                "currency_code": row.currency_code,
                "rate_to_usd": row.rate_to_usd,
                "updated_at": row.updated_at.isoformat(),
            }
            for row in currency_rows
        ],
        "system_settings": [
            {
                "key": row.key,
                "value": row.value,
                "updated_at": row.updated_at.isoformat(),
            }
            for row in setting_rows
        ],
        "sku_sequences": [
            {
                "sequence_key": row.sequence_key,
                "last_value": row.last_value,
            }
            for row in sku_rows
        ],
        "product_price_history": [
            {
                "id": row.id,
                "product_id": row.product_id,
                "changed_by": row.changed_by,
                "reason": row.reason,
                "currency_code": row.currency_code,
                "old_cost_amount": row.old_cost_amount,
                "new_cost_amount": row.new_cost_amount,
                "old_base_price_amount": row.old_base_price_amount,
                "new_base_price_amount": row.new_base_price_amount,
                "old_base_discount_pct": row.old_base_discount_pct,
                "new_base_discount_pct": row.new_base_discount_pct,
                "created_at": row.created_at.isoformat(),
            }
            for row in price_history_rows
        ],
    }


@router.post("/security/restore")
def restore_security_backup(
    payload: dict,
    replace_data: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("settings:write")),
) -> dict:
    ensure_admin_user(db, current_user)

    backup_format = str(payload.get("format") or "")
    if backup_format not in {"ridax-backup-v1", "ridax-backup-v2"}:
        raise HTTPException(status_code=400, detail="Formato de respaldo invalido")

    sales_data = payload.get("sales") or []
    inventory_data = payload.get("inventory_snapshot") or []
    movement_data = payload.get("inventory_movements") or []
    purchases_data = payload.get("purchases") or []
    currency_data = payload.get("currency_rates") or []
    settings_data = payload.get("system_settings") or []
    sku_data = payload.get("sku_sequences") or []
    price_history_data = payload.get("product_price_history") or []
    if (
        not isinstance(sales_data, list)
        or not isinstance(inventory_data, list)
        or not isinstance(movement_data, list)
        or not isinstance(purchases_data, list)
        or not isinstance(currency_data, list)
        or not isinstance(settings_data, list)
        or not isinstance(sku_data, list)
        or not isinstance(price_history_data, list)
    ):
        raise HTTPException(status_code=400, detail="Estructura de respaldo invalida")

    if replace_data:
        db.execute(delete(ProductPriceHistory))
        db.execute(delete(Purchase))
        db.execute(delete(Sale))
        db.execute(delete(InventoryMovement))
        if backup_format == "ridax-backup-v2":
            db.execute(delete(CurrencyRate))
            db.execute(delete(SystemSetting))
            db.execute(delete(SkuSequence))
        db.commit()

    updated_currency_rates = 0
    updated_system_settings = 0
    updated_sku_sequences = 0

    if backup_format == "ridax-backup-v2":
        for item in currency_data:
            if not isinstance(item, dict):
                continue
            code = str(item.get("currency_code") or "").upper().strip()
            if not code:
                continue
            rate_value = item.get("rate_to_usd")
            if not isinstance(rate_value, (int, float)):
                continue
            row = db.scalar(select(CurrencyRate).where(CurrencyRate.currency_code == code))
            if not row:
                row = CurrencyRate(currency_code=code, rate_to_usd=float(rate_value))
                db.add(row)
            else:
                row.rate_to_usd = float(rate_value)
            row.updated_at = parse_iso_datetime(str(item.get("updated_at") or ""))
            updated_currency_rates += 1

        for item in settings_data:
            if not isinstance(item, dict):
                continue
            key = str(item.get("key") or "").strip()
            if not key:
                continue
            value = str(item.get("value") or "")
            row = db.scalar(select(SystemSetting).where(SystemSetting.key == key))
            if not row:
                row = SystemSetting(key=key, value=value)
                db.add(row)
            else:
                row.value = value
            row.updated_at = parse_iso_datetime(str(item.get("updated_at") or ""))
            updated_system_settings += 1

        for item in sku_data:
            if not isinstance(item, dict):
                continue
            sequence_key = str(item.get("sequence_key") or "").strip()
            if not sequence_key:
                continue
            last_value = item.get("last_value")
            if not isinstance(last_value, int):
                continue
            row = db.scalar(select(SkuSequence).where(SkuSequence.sequence_key == sequence_key))
            if not row:
                row = SkuSequence(sequence_key=sequence_key, last_value=last_value)
                db.add(row)
            else:
                row.last_value = last_value
            updated_sku_sequences += 1

        usd_rate = db.scalar(select(CurrencyRate).where(CurrencyRate.currency_code == "USD"))
        if not usd_rate:
            db.add(CurrencyRate(currency_code="USD", rate_to_usd=1.0))

    product_rows = db.scalars(select(Product)).all()
    products_by_id = {row.id: row for row in product_rows}
    products_by_sku = {row.sku: row for row in product_rows}
    product_id_map: dict[int, int] = {}

    updated_products = 0
    for item in inventory_data:
        if not isinstance(item, dict):
            continue
        product = None
        product_id = item.get("product_id")
        if isinstance(product_id, int):
            product = products_by_id.get(product_id)
        if not product and item.get("sku"):
            product = products_by_sku.get(str(item.get("sku")))
        if not product:
            sku = str(item.get("sku") or "").strip()
            name = str(item.get("name") or "").strip()
            if not sku or not name:
                continue
            product = Product(
                sku=sku,
                name=name,
                product_type=str(item.get("product_type") or ""),
                brand=str(item.get("brand") or ""),
                model=str(item.get("model") or ""),
                currency_code=str(item.get("currency_code") or "USD").upper(),
                final_customer_price=float(item.get("final_customer_price") or 0),
                wholesale_price=float(item.get("wholesale_price") or 0),
                retail_price=float(item.get("retail_price") or 0),
                base_price_amount=float(item.get("retail_price") or 0),
                price_usd=float(item.get("final_customer_price") or 0),
                stock=int(item.get("stock") or 0),
                is_active=bool(item.get("is_active", True)),
            )
            if isinstance(product_id, int) and product_id > 0 and product_id not in products_by_id:
                product.id = product_id
            db.add(product)
            db.flush()
            products_by_id[product.id] = product
            products_by_sku[product.sku] = product

        if isinstance(product_id, int):
            product_id_map[product_id] = product.id

        stock_value = item.get("stock")
        if isinstance(stock_value, (int, float)):
            product.stock = int(stock_value)
        if isinstance(item.get("product_type"), str):
            product.product_type = item["product_type"]
        if isinstance(item.get("brand"), str):
            product.brand = item["brand"]
        if isinstance(item.get("model"), str):
            product.model = item["model"]
        if isinstance(item.get("currency_code"), str):
            product.currency_code = item["currency_code"].upper()
        if isinstance(item.get("wholesale_price"), (int, float)):
            product.wholesale_price = float(item["wholesale_price"])
        if isinstance(item.get("retail_price"), (int, float)):
            product.retail_price = float(item["retail_price"])
        if isinstance(item.get("final_customer_price"), (int, float)):
            product.final_customer_price = float(item["final_customer_price"])
        if isinstance(item.get("is_active"), bool):
            product.is_active = item["is_active"]
        updated_products += 1

    existing_purchase_fingerprints = {
        f"{row.product_id}:{row.quantity}:{row.total_usd}:{row.created_at.isoformat()}"
        for row in db.scalars(select(Purchase)).all()
    }
    added_purchases = 0
    for item in purchases_data:
        if not isinstance(item, dict):
            continue
        old_product_id = item.get("product_id")
        if not isinstance(old_product_id, int):
            continue
        product_id = product_id_map.get(old_product_id, old_product_id)
        if product_id not in products_by_id:
            continue
        created_at_raw = str(item.get("created_at") or "")
        fingerprint = (
            f"{product_id}:{int(item.get('quantity') or 0)}:{float(item.get('total_usd') or 0)}:{created_at_raw}"
        )
        if not replace_data and fingerprint in existing_purchase_fingerprints:
            continue

        db.add(
            Purchase(
                product_id=product_id,
                quantity=max(1, int(item.get("quantity") or 1)),
                unit_cost_usd=float(item.get("unit_cost_usd") or 0),
                total_usd=float(item.get("total_usd") or 0),
                supplier_name=str(item.get("supplier_name") or ""),
                purchase_note=str(item.get("purchase_note") or ""),
                created_by=int(item.get("created_by") or current_user.id),
                created_at=parse_iso_datetime(created_at_raw),
            )
        )
        added_purchases += 1

    existing_fingerprints = {
        f"{row.invoice_code}:{row.product_id}:{row.quantity}:{row.total_usd}:{row.created_at.isoformat()}"
        for row in db.scalars(select(Sale)).all()
    }
    added_sales = 0
    for item in sales_data:
        if not isinstance(item, dict):
            continue
        try:
            fingerprint = (
                f"{item.get('invoice_code')}:{int(item.get('product_id', 0))}:"
                f"{int(item.get('quantity', 0))}:{float(item.get('total_usd', 0))}:"
                f"{str(item.get('created_at') or '')}"
            )
        except (TypeError, ValueError):
            continue

        if not replace_data and fingerprint in existing_fingerprints:
            continue

        old_product_id = item.get("product_id")
        if not isinstance(old_product_id, int):
            continue
        product_id = product_id_map.get(old_product_id, old_product_id)
        if product_id not in products_by_id:
            continue

        db.add(
            Sale(
                invoice_code=str(item.get("invoice_code") or f"REST-{datetime.now(timezone.utc).timestamp()}"),
                product_id=product_id,
                quantity=max(1, int(item.get("quantity") or 1)),
                currency_code=str(item.get("currency_code") or "USD").upper(),
                unit_price_usd=float(item.get("unit_price_usd") or 0),
                subtotal_usd=float(item.get("subtotal_usd") or 0),
                discount_pct=float(item.get("discount_pct") or 0),
                discount_amount_usd=float(item.get("discount_amount_usd") or 0),
                tax_pct=float(item.get("tax_pct") or 0),
                tax_amount_usd=float(item.get("tax_amount_usd") or 0),
                total_usd=float(item.get("total_usd") or 0),
                customer_name=str(item.get("customer_name") or ""),
                customer_phone=str(item.get("customer_phone") or ""),
                customer_address=str(item.get("customer_address") or ""),
                customer_rif=str(item.get("customer_rif") or ""),
                seller_user_id=int(item.get("seller_user_id")) if item.get("seller_user_id") is not None else None,
                sale_date=parse_iso_datetime(str(item.get("sale_date") or "")) if item.get("sale_date") else None,
                payment_currency_code=str(item.get("payment_currency_code") or "USD").upper(),
                payment_amount=float(item.get("payment_amount") or 0),
                payment_rate_to_usd=float(item.get("payment_rate_to_usd") or 0),
                payment_amount_usd=float(item.get("payment_amount_usd") or 0),
                manual_total_override=bool(item.get("manual_total_override", False)),
                manual_total_input_usd=float(item.get("manual_total_input_usd")) if item.get("manual_total_input_usd") is not None else None,
                manual_total_original_usd=float(item.get("manual_total_original_usd")) if item.get("manual_total_original_usd") is not None else None,
                manual_total_set_by=int(item.get("manual_total_set_by")) if item.get("manual_total_set_by") is not None else None,
                manual_total_set_at=parse_iso_datetime(str(item.get("manual_total_set_at") or "")) if item.get("manual_total_set_at") else None,
                commission_pct=float(item.get("commission_pct") or 0),
                commission_amount_usd=float(item.get("commission_amount_usd") or 0),
                is_voided=bool(item.get("is_voided", False)),
                voided_at=parse_iso_datetime(str(item.get("voided_at") or "")) if item.get("voided_at") else None,
                voided_by=int(item.get("voided_by")) if item.get("voided_by") is not None else None,
                void_reason=str(item.get("void_reason") or ""),
                created_by=int(item.get("created_by") or current_user.id),
                created_at=parse_iso_datetime(str(item.get("created_at") or "")),
            )
        )
        added_sales += 1

    existing_movements = {
        f"{row.product_id}:{row.movement_type}:{row.quantity}:{row.note}:{row.created_at.isoformat()}"
        for row in db.scalars(select(InventoryMovement)).all()
    }
    added_movements = 0
    for item in movement_data:
        if not isinstance(item, dict):
            continue
        old_product_id = item.get("product_id")
        if not isinstance(old_product_id, int):
            continue
        product_id = product_id_map.get(old_product_id, old_product_id)
        if product_id not in products_by_id:
            continue

        movement_type = str(item.get("movement_type") or "adjustment_in")
        quantity = int(item.get("quantity") or 0)
        note = str(item.get("note") or "")
        created_at_raw = str(item.get("created_at") or "")
        fingerprint = f"{product_id}:{movement_type}:{quantity}:{note}:{created_at_raw}"
        if not replace_data and fingerprint in existing_movements:
            continue

        db.add(
            InventoryMovement(
                product_id=product_id,
                movement_type=movement_type,
                quantity=quantity,
                note=note,
                created_by=int(item.get("created_by") or current_user.id),
                created_at=parse_iso_datetime(created_at_raw),
            )
        )
        added_movements += 1

    existing_history_fingerprints = {
        f"{row.product_id}:{row.changed_by}:{row.reason}:{row.new_base_price_amount}:{row.created_at.isoformat()}"
        for row in db.scalars(select(ProductPriceHistory)).all()
    }
    added_price_history = 0
    for item in price_history_data:
        if not isinstance(item, dict):
            continue
        old_product_id = item.get("product_id")
        if not isinstance(old_product_id, int):
            continue
        product_id = product_id_map.get(old_product_id, old_product_id)
        if product_id not in products_by_id:
            continue

        created_at_raw = str(item.get("created_at") or "")
        fingerprint = (
            f"{product_id}:{int(item.get('changed_by') or current_user.id)}:{str(item.get('reason') or '')}:"
            f"{float(item.get('new_base_price_amount') or 0)}:{created_at_raw}"
        )
        if not replace_data and fingerprint in existing_history_fingerprints:
            continue

        db.add(
            ProductPriceHistory(
                product_id=product_id,
                changed_by=int(item.get("changed_by") or current_user.id),
                reason=str(item.get("reason") or ""),
                currency_code=str(item.get("currency_code") or "USD").upper(),
                old_cost_amount=float(item.get("old_cost_amount") or 0),
                new_cost_amount=float(item.get("new_cost_amount") or 0),
                old_base_price_amount=float(item.get("old_base_price_amount") or 0),
                new_base_price_amount=float(item.get("new_base_price_amount") or 0),
                old_base_discount_pct=float(item.get("old_base_discount_pct") or 0),
                new_base_discount_pct=float(item.get("new_base_discount_pct") or 0),
                created_at=parse_iso_datetime(created_at_raw),
            )
        )
        added_price_history += 1

    db.commit()
    return {
        "message": "Respaldo restaurado",
        "replace_data": replace_data,
        "format": backup_format,
        "updated_products": updated_products,
        "updated_currency_rates": updated_currency_rates,
        "updated_system_settings": updated_system_settings,
        "updated_sku_sequences": updated_sku_sequences,
        "added_purchases": added_purchases,
        "added_sales": added_sales,
        "added_inventory_movements": added_movements,
        "added_product_price_history": added_price_history,
    }
