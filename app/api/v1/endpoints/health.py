from fastapi import APIRouter, status
from app.core.config import settings
from app.core.database import db_manager

router = APIRouter()


@router.get("/health", status_code=status.HTTP_200_OK, tags=["Sistema"])
async def health_check():
    """
    Verifica el estado del servicio y la conectividad con MongoDB.
    """
    db_connected = False
    db_details = "Desconectado"

    if db_manager.client:
        try:
            await db_manager.client.admin.command('ping')
            db_connected = True
            db_details = f"Conectado a '{settings.MONGODB_DB_NAME}'"
        except Exception as e:
            db_details = f"Error: {str(e)}"

    return {
        "status": "healthy" if db_connected else "degraded",
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "database": {
            "connected": db_connected,
            "details": db_details
        }
    }
