from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.currency import CurrencyRate
from app.models.product import Product
from app.models.system_setting import SystemSetting
from app.models.role import Role
from app.models.user import User
from app.services.rbac import ROLE_PERMISSIONS, serialize_permissions


def seed_initial_data(db: Session) -> None:
    role_count = db.query(Role).count()
    if role_count == 0:
        for role_name in ROLE_PERMISSIONS:
            db.add(Role(name=role_name, permissions=serialize_permissions(role_name)))
        db.commit()

    user_count = db.query(User).count()
    if user_count == 0:
        roles = {role.name: role for role in db.scalars(select(Role)).all()}
        db.add_all(
            [
                User(
                    email="admin@ridax.local",
                    full_name="Administrador RIDAX",
                    hashed_password=hash_password("Admin123!"),
                    role_id=roles["Admin"].id,
                ),
                User(
                    email="gerente@ridax.local",
                    full_name="Gerente RIDAX",
                    hashed_password=hash_password("Gerente123!"),
                    role_id=roles["Gerente"].id,
                ),
                User(
                    email="vendedor@ridax.local",
                    full_name="Vendedor RIDAX",
                    hashed_password=hash_password("Vendedor123!"),
                    role_id=roles["Vendedor"].id,
                ),
            ]
        )
        db.commit()

    product_count = db.query(Product).count()
    if product_count == 0:
        db.add_all(
            [
                Product(
                    sku="RIDAX-001",
                    name="Aceite Sintetico RIDAX 5W30",
                    product_type="Lubricante",
                    brand="RIDAX",
                    model="5W30",
                    measure_quantity=1,
                    measure_unit="L",
                    description="Envase 1L para alto rendimiento.",
                    cost_amount=10.0,
                    base_price_amount=15.5,
                    base_discount_pct=5,
                    final_customer_price=14.5,
                    wholesale_price=13.2,
                    retail_price=15.5,
                    currency_code="USD",
                    price_usd=14.5,
                    stock=40,
                ),
                Product(
                    sku="RIDAX-002",
                    name="Filtro Premium RIDAX",
                    product_type="Filtro",
                    brand="RIDAX",
                    model="SED-SUV",
                    measure_quantity=1,
                    measure_unit="unidad",
                    description="Compatible con lineas sedan y SUV.",
                    cost_amount=5.6,
                    base_price_amount=8.7,
                    base_discount_pct=5,
                    final_customer_price=8.25,
                    wholesale_price=7.9,
                    retail_price=8.7,
                    currency_code="USD",
                    price_usd=8.25,
                    stock=65,
                ),
            ]
        )
        db.commit()

    rates_count = db.query(CurrencyRate).count()
    if rates_count == 0:
        db.add_all(
            [
                CurrencyRate(currency_code="USD", rate_to_usd=1.0),
                CurrencyRate(currency_code="EUR", rate_to_usd=0.92),
                CurrencyRate(currency_code="VES", rate_to_usd=36.5),
                CurrencyRate(currency_code="MXN", rate_to_usd=17.0),
            ]
        )
        db.commit()

    ves_rate = db.query(CurrencyRate).filter(CurrencyRate.currency_code == "VES").first()
    if not ves_rate:
        db.add(CurrencyRate(currency_code="VES", rate_to_usd=36.5))
        db.commit()

    setting = db.query(SystemSetting).filter(SystemSetting.key == "operational_currency").first()
    if not setting:
        db.add(SystemSetting(key="operational_currency", value="USD"))
        db.commit()

    defaults = {
        "receipt_company_name": "RIDAX",
        "receipt_company_phone": "",
        "receipt_company_address": "",
        "receipt_company_rif": "",
        "modules_enabled_default": '["dashboard","articles","inventory","sales","purchases","reports","settings"]',
        "show_discount_in_invoice": "true",
        "sales_rounding_mode": "none",
        "default_markup_percent": "20",
        "invoice_tax_enabled": "false",
        "invoice_tax_percent": "16",
        "ui_theme_mode": "dark",
    }
    for key, value in defaults.items():
        row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
        if not row:
            db.add(SystemSetting(key=key, value=value))
    db.commit()
