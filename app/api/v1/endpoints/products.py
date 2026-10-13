from datetime import datetime
from typing import List, Optional
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from app.api.v1.endpoints.auth import get_current_user
from app.core.database import get_database

router = APIRouter(prefix="/products", tags=["Catálogo de Productos"])


class ProductCreateRequest(BaseModel):
    sku_code: str
    nombre: str
    categoria: str
    proveedor_id: str
    almacen_id: Optional[str] = None
    costo_unitario: float
    precio_venta: float
    stock_actual: int
    stock_seguridad: int = 0
    moq: int = 1
    incremento_lote: int = 1
    volumen_cm3: float
    peso_kg: float = 0.0
    lead_time_promedio_dias: int = 7


class ProductUpdateRequest(BaseModel):
    nombre: Optional[str] = None
    costo_unitario: Optional[float] = None
    precio_venta: Optional[float] = None
    stock_actual: Optional[int] = None
    stock_seguridad: Optional[int] = None
    moq: Optional[int] = None
    lead_time_promedio_dias: int = None
    estado: Optional[str] = None


@router.get("/")
async def list_products(
    categoria: Optional[str] = Query(None),
    estado: Optional[str] = Query("ACTIVO"),
    limit: int = Query(50, le=500),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user)
):
    """Lista los productos del catálogo con filtros opcionales."""
    db = get_database()
    query = {}
    if categoria:
        query["categoria"] = categoria
    if estado:
        query["estado"] = estado

    cursor = db["productos"].find(query).skip(skip).limit(limit)
    products = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        if "proveedor_id" in doc:
            doc["proveedor_id"] = str(doc["proveedor_id"])
        if "almacen_id" in doc and doc["almacen_id"]:
            doc["almacen_id"] = str(doc["almacen_id"])
        products.append(doc)

    total = await db["productos"].count_documents(query)
    return {"total": total, "items": products}


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_product(
    prod_in: ProductCreateRequest,
    current_user: dict = Depends(get_current_user)
):
    """Crea un nuevo producto en el catálogo maestro."""
    db = get_database()
    existing = await db["productos"].find_one({"sku_code": prod_in.sku_code})
    if existing:
        raise HTTPException(status_code=400, detail=f"El SKU '{prod_in.sku_code}' ya existe.")

    doc = prod_in.model_dump()
    doc["proveedor_id"] = ObjectId(prod_in.proveedor_id)
    if prod_in.almacen_id:
        doc["almacen_id"] = ObjectId(prod_in.almacen_id)
    doc["estado"] = "ACTIVO"
    doc["audit"] = {
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }

    result = await db["productos"].insert_one(doc)
    return {"message": "Producto creado", "id": str(result.inserted_id), "sku_code": prod_in.sku_code}


@router.post("/batch", status_code=status.HTTP_201_CREATED)
async def batch_upload_products(
    products_in: List[ProductCreateRequest],
    current_user: dict = Depends(get_current_user)
):
    """Ingesta masiva de catálogo de productos (RF01)."""
    db = get_database()
    inserted_ids = []
    errors = []

    for item in products_in:
        try:
            existing = await db["productos"].find_one({"sku_code": item.sku_code})
            if existing:
                errors.append(f"SKU {item.sku_code} ya existe.")
                continue
            doc = item.model_dump()
            doc["proveedor_id"] = ObjectId(item.proveedor_id)
            if item.almacen_id:
                doc["almacen_id"] = ObjectId(item.almacen_id)
            doc["estado"] = "ACTIVO"
            doc["audit"] = {
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            res = await db["productos"].insert_one(doc)
            inserted_ids.append(str(res.inserted_id))
        except Exception as e:
            errors.append(f"Error procesando SKU {item.sku_code}: {str(e)}")

    return {
        "insertados": len(inserted_ids),
        "errores": errors
    }
