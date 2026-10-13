from datetime import datetime
from typing import List, Optional
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field
from app.api.v1.endpoints.auth import get_current_user
from app.core.database import get_database

router = APIRouter(prefix="/suppliers", tags=["Proveedores"])


class ContactoIn(BaseModel):
    nombre: str
    email: EmailStr
    telefono: Optional[str] = None


class SupplierCreateRequest(BaseModel):
    codigo_proveedor: str
    nombre_empresa: str
    contacto: Optional[ContactoIn] = None
    moneda: str = "USD"
    condiciones_pago: str = "30_DIAS"
    calificacion_calidad: float = Field(default=5.0, ge=1.0, le=5.0)
    variabilidad_lead_time_dias: float = 0.0
    lead_time_promedio_dias: int = 7


@router.get("/")
async def list_suppliers(
    estado: Optional[str] = Query("ACTIVO"),
    current_user: dict = Depends(get_current_user)
):
    """Lista todos los proveedores registrados."""
    db = get_database()
    query = {}
    if estado:
        query["estado"] = estado
    cursor = db["proveedores"].find(query)
    suppliers = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        suppliers.append(doc)
    return {"total": len(suppliers), "items": suppliers}


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_supplier(
    supp_in: SupplierCreateRequest,
    current_user: dict = Depends(get_current_user)
):
    """Crea un nuevo proveedor."""
    db = get_database()
    existing = await db["proveedores"].find_one({"codigo_proveedor": supp_in.codigo_proveedor})
    if existing:
        raise HTTPException(status_code=400, detail=f"El proveedor con código '{supp_in.codigo_proveedor}' ya existe.")

    doc = supp_in.model_dump()
    doc["estado"] = "ACTIVO"
    doc["created_at"] = datetime.utcnow()
    result = await db["proveedores"].insert_one(doc)
    return {"message": "Proveedor registrado", "id": str(result.inserted_id), "codigo": supp_in.codigo_proveedor}
