import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text
from sqlalchemy.exc import OperationalError

from app.api.routes import api_router
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.services.seed import seed_initial_data


settings = get_settings()
app = FastAPI(title=settings.app_name)


def apply_runtime_schema_updates() -> None:
    sales_columns = {column["name"] for column in inspect(engine).get_columns("sales")}
    statements: list[str] = []
    if "seller_user_id" not in sales_columns:
        statements.append("ALTER TABLE sales ADD COLUMN seller_user_id INTEGER")
    if "sale_date" not in sales_columns:
        statements.append("ALTER TABLE sales ADD COLUMN sale_date TIMESTAMP WITH TIME ZONE")
    if "payment_currency_code" not in sales_columns:
        statements.append("ALTER TABLE sales ADD COLUMN payment_currency_code VARCHAR(10)")
    if "payment_amount" not in sales_columns:
        statements.append("ALTER TABLE sales ADD COLUMN payment_amount DOUBLE PRECISION")
    if "payment_rate_to_usd" not in sales_columns:
        statements.append("ALTER TABLE sales ADD COLUMN payment_rate_to_usd DOUBLE PRECISION")
    if "payment_amount_usd" not in sales_columns:
        statements.append("ALTER TABLE sales ADD COLUMN payment_amount_usd DOUBLE PRECISION")
    if "manual_total_override" not in sales_columns:
        statements.append("ALTER TABLE sales ADD COLUMN manual_total_override BOOLEAN DEFAULT FALSE")
    if "manual_total_input_usd" not in sales_columns:
        statements.append("ALTER TABLE sales ADD COLUMN manual_total_input_usd DOUBLE PRECISION")
    if "manual_total_original_usd" not in sales_columns:
        statements.append("ALTER TABLE sales ADD COLUMN manual_total_original_usd DOUBLE PRECISION")
    if "manual_total_set_by" not in sales_columns:
        statements.append("ALTER TABLE sales ADD COLUMN manual_total_set_by INTEGER")
    if "manual_total_set_at" not in sales_columns:
        statements.append("ALTER TABLE sales ADD COLUMN manual_total_set_at TIMESTAMP WITH TIME ZONE")
    if "commission_pct" not in sales_columns:
        statements.append("ALTER TABLE sales ADD COLUMN commission_pct DOUBLE PRECISION DEFAULT 0")
    if "commission_amount_usd" not in sales_columns:
        statements.append("ALTER TABLE sales ADD COLUMN commission_amount_usd DOUBLE PRECISION DEFAULT 0")
    if "is_voided" not in sales_columns:
        statements.append("ALTER TABLE sales ADD COLUMN is_voided BOOLEAN DEFAULT FALSE")
    if "voided_at" not in sales_columns:
        statements.append("ALTER TABLE sales ADD COLUMN voided_at TIMESTAMP WITH TIME ZONE")
    if "voided_by" not in sales_columns:
        statements.append("ALTER TABLE sales ADD COLUMN voided_by INTEGER")
    if "void_reason" not in sales_columns:
        statements.append("ALTER TABLE sales ADD COLUMN void_reason VARCHAR(255) DEFAULT ''")

    if not statements:
        return

    with engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))

origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event() -> None:
    retries = 20
    while retries > 0:
        try:
            Base.metadata.create_all(bind=engine)
            apply_runtime_schema_updates()
            break
        except OperationalError:
            retries -= 1
            if retries == 0:
                raise
            time.sleep(1)

    db = SessionLocal()
    try:
        seed_initial_data(db)
    finally:
        db.close()


@app.get("/")
def root() -> dict:
    return {
        "name": "RIDAX Platform API",
        "version": "0.1.0",
        "docs": "/docs",
    }


app.include_router(api_router, prefix=settings.api_v1_prefix)
