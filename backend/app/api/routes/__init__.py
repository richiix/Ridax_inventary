from fastapi import APIRouter

from app.api.routes import (
    articles,
    auth,
    dashboard,
    integrations,
    inventory,
    public,
    purchases,
    reports,
    sales,
    settings,
)


api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
api_router.include_router(articles.router, prefix="/articles", tags=["Articulos"])
api_router.include_router(inventory.router, prefix="/inventory", tags=["Inventario"])
api_router.include_router(sales.router, prefix="/sales", tags=["Ventas"])
api_router.include_router(purchases.router, prefix="/purchases", tags=["Compras"])
api_router.include_router(reports.router, prefix="/reports", tags=["Informes"])
api_router.include_router(settings.router, prefix="/settings", tags=["Configuracion"])
api_router.include_router(integrations.router, prefix="/integrations", tags=["Integraciones"])
api_router.include_router(public.router, prefix="/public", tags=["Public"])
