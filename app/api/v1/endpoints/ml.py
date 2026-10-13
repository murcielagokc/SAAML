from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from app.api.v1.endpoints.auth import get_current_user
from app.core.database import get_database
from app.services.ml_engine import ml_forecaster

router = APIRouter(prefix="/ml", tags=["Machine Learning (RF02, RF06)"])


@router.post("/train", status_code=status.HTTP_200_OK)
async def train_models(current_user: dict = Depends(get_current_user)):
    """
    Ejecuta el pipeline de reentrenamiento de Machine Learning (RF06).
    Procesa las series de tiempo de 'historial_ventas' en MongoDB Atlas,
    calcula métricas de error (MAPE, RMSE, MAE) y actualiza el modelo en producción.
    """
    try:
        resultado = await ml_forecaster.train_and_evaluate()
        return {
            "message": "Entrenamiento de Machine Learning completado exitosamente",
            "resultado": resultado
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en entrenamiento: {str(e)}")


@router.get("/forecast/{sku_code}")
async def forecast_single_sku(
    sku_code: str,
    horizon_days: int = Query(14, ge=1, le=90, description="Días hacia el futuro a proyectar"),
    current_user: dict = Depends(get_current_user)
):
    """
    Proyecta la demanda esperada para un SKU en los próximos N días (RF02).
    """
    try:
        forecast = await ml_forecaster.forecast_sku(sku_code=sku_code, horizon_days=horizon_days)
        return forecast
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al generar predicción: {str(e)}")


@router.get("/forecast-all")
async def forecast_all_catalog(
    horizon_days: int = Query(14, ge=1, le=90),
    current_user: dict = Depends(get_current_user)
):
    """
    Genera el pronóstico de demanda de todos los productos del catálogo activo.
    Esta data es el insumo directo que alimenta el optimizador Knapsack (RF04).
    """
    db = get_database()
    products = await db["productos"].find({"estado": "ACTIVO"}).to_list(length=200)
    projections = []

    for p in products:
        sku = p["sku_code"]
        try:
            fc = await ml_forecaster.forecast_sku(sku_code=sku, horizon_days=horizon_days)
            projections.append(fc)
        except Exception:
            continue

    return {
        "horizonte_dias": horizon_days,
        "total_skus": len(projections),
        "proyecciones": projections
    }


@router.get("/models")
async def list_model_audits(current_user: dict = Depends(get_current_user)):
    """
    Consulta la trazabilidad y métricas de error de los modelos entrenados (MLOps / RF06).
    """
    db = get_database()
    cursor = db["modelos_ml"].find().sort("fecha_entrenamiento", -1)
    audits = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        audits.append(doc)
    return {"total": len(audits), "modelos": audits}
