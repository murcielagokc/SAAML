from datetime import datetime
from typing import List, Optional
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from app.api.v1.endpoints.auth import get_current_user
from app.core.database import get_database

router = APIRouter(prefix="/budget", tags=["Ciclos Presupuestales (RF03)"])


class BudgetCycleCreateRequest(BaseModel):
    codigo_ciclo: str
    periodo: str
    fecha_inicio: datetime
    fecha_fin: datetime
    presupuesto_total_asignado: float


@router.get("/")
async def list_budget_cycles(
    estado: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user)
):
    """Lista todos los ciclos presupuestales registrados."""
    db = get_database()
    query = {}
    if estado:
        query["estado"] = estado
    cursor = db["ciclos_presupuestales"].find(query).sort("fecha_inicio", -1)
    cycles = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        if "created_by" in doc and doc["created_by"]:
            doc["created_by"] = str(doc["created_by"])
        cycles.append(doc)
    return {"total": len(cycles), "items": cycles}


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_budget_cycle(
    cycle_in: BudgetCycleCreateRequest,
    current_user: dict = Depends(get_current_user)
):
    """Crea un nuevo ciclo de restricción presupuestal (RF03)."""
    db = get_database()
    existing = await db["ciclos_presupuestales"].find_one({"codigo_ciclo": cycle_in.codigo_ciclo})
    if existing:
        raise HTTPException(status_code=400, detail=f"El ciclo '{cycle_in.codigo_ciclo}' ya existe.")

    doc = cycle_in.model_dump()
    doc["presupuesto_comprometido"] = 0.0
    doc["presupuesto_consumido_real"] = 0.0
    doc["estado"] = "ABIERTO"
    doc["created_by"] = current_user["_id"]
    doc["created_at"] = datetime.utcnow()

    result = await db["ciclos_presupuestales"].insert_one(doc)
    return {
        "message": "Ciclo presupuestal creado exitosamente",
        "id": str(result.inserted_id),
        "codigo_ciclo": cycle_in.codigo_ciclo
    }
