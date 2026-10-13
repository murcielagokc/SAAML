from typing import Optional
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from app.api.v1.endpoints.auth import get_current_user
from app.core.database import get_database
from app.services.optimizer import optimizer_engine

router = APIRouter(prefix="/optimization", tags=["Optimización Presupuestal (RF04, RNF01)"])


class OptimizationRunRequest(BaseModel):
    ciclo_presupuestal_id: str
    presupuesto_limite: Optional[float] = Field(None, gt=0, description="Límite presupuestal opcional. Si no se envía, usa el saldo disponible del ciclo.")
    horizon_days: int = Field(14, ge=1, le=90, description="Días hacia el futuro a proyectar la demanda")
    considerar_volumen_almacen: bool = Field(True, description="Si es True, aplica restricción de capacidad volumétrica de almacén")
    factor_seguridad: float = Field(1.0, ge=0.0, le=3.0, description="Multiplicador sobre el stock de seguridad base")


@router.post("/run", status_code=status.HTTP_200_OK)
async def run_optimization(
    request: OptimizationRunRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Ejecuta el modelo de investigación de operaciones (Knapsack Multiobjetivo / MILP)
    para priorizar compras respetando restricciones de presupuesto, MOQ, lote y volumen (RF04, RNF01).
    """
    try:
        session_result = await optimizer_engine.optimize(
            ciclo_presupuestal_id=request.ciclo_presupuestal_id,
            user_id=current_user["_id"],
            presupuesto_limite=request.presupuesto_limite,
            horizon_days=request.horizon_days,
            considerar_volumen_almacen=request.considerar_volumen_almacen,
            factor_seguridad=request.factor_seguridad
        )
        return {
            "message": "Sesión de optimización ejecutada exitosamente",
            "sesion": session_result
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al ejecutar optimizador: {str(e)}")


@router.get("/sessions")
async def list_optimization_sessions(
    ciclo_id: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    """
    Lista las sesiones de optimización realizadas históricamente (RNF01).
    """
    db = get_database()
    query = {}
    if ciclo_id:
        try:
            query["ciclo_presupuestal_id"] = ObjectId(ciclo_id)
        except Exception:
            raise HTTPException(status_code=400, detail="ID de ciclo inválido")

    cursor = db["sesiones_optimizacion"].find(query).sort("fecha_ejecucion", -1).limit(limit)
    sessions = []
    async for s in cursor:
        s["_id"] = str(s["_id"])
        s["ciclo_presupuestal_id"] = str(s["ciclo_presupuestal_id"])
        s["usuario_id"] = str(s["usuario_id"])
        sessions.append(s)

    return {"total": len(sessions), "items": sessions}


@router.get("/sessions/{session_id}")
async def get_optimization_session(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Consulta los detalles completos de una sesión de optimización específica por ID.
    """
    db = get_database()
    try:
        oid = ObjectId(session_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID de sesión inválido")

    session = await db["sesiones_optimizacion"].find_one({"_id": oid})
    if not session:
        raise HTTPException(status_code=404, detail="Sesión de optimización no encontrada")

    session["_id"] = str(session["_id"])
    session["ciclo_presupuestal_id"] = str(session["ciclo_presupuestal_id"])
    session["usuario_id"] = str(session["usuario_id"])
    return session
