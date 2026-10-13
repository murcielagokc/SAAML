from fastapi import APIRouter
from app.api.v1.endpoints import auth, budget, health, ml, optimization, orders, products, sales, suppliers

api_router = APIRouter()

# Registrar submódulos de la API v1
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(products.router)
api_router.include_router(suppliers.router)
api_router.include_router(sales.router)
api_router.include_router(budget.router)
api_router.include_router(ml.router)
api_router.include_router(optimization.router)
api_router.include_router(orders.router)

