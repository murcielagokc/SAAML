from datetime import datetime
from typing import List, Optional
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from app.api.v1.endpoints.auth import get_current_user
from app.core.database import get_database

router = APIRouter(prefix="/sales", tags=["Historial de Ventas"])


class SaleItemIn(BaseModel):
    sku_code: str
    fecha: datetime
    cantidad_vendida: int
    precio_unitario_aplicado: float
    descuento_porcentaje: float = 0.0
    stockout_flag: bool = False
    canal_venta: str = "RETAIL"


@router.post("/batch", status_code=status.HTTP_201_CREATED)
async def upload_sales_batch(
    sales: List[SaleItemIn],
    current_user: dict = Depends(get_current_user)
):
    """
    Ingesta masiva de datos históricos de ventas (RF01).
    Relaciona automáticamente el sku_code con su respectivo ObjectId.
    """
    db = get_database()
    if not sales:
        raise HTTPException(status_code=400, detail="La lista de ventas no puede estar vacía.")

    # Cache de SKUs a ObjectId
    unique_skus = list({s.sku_code for s in sales})
    sku_docs = await db["productos"].find({"sku_code": {"$in": unique_skus}}).to_list(length=len(unique_skus))
    sku_map = {doc["sku_code"]: doc["_id"] for doc in sku_docs}

    docs_to_insert = []
    missing_skus = set()

    for s in sales:
        if s.sku_code not in sku_map:
            missing_skus.add(s.sku_code)
            continue
        docs_to_insert.append({
            "sku_id": sku_map[s.sku_code],
            "fecha": s.fecha,
            "cantidad_vendida": s.cantidad_vendida,
            "precio_unitario_aplicado": s.precio_unitario_aplicado,
            "descuento_porcentaje": s.descuento_porcentaje,
            "stockout_flag": s.stockout_flag,
            "canal_venta": s.canal_venta
        })

    inserted_count = 0
    if docs_to_insert:
        res = await db["historial_ventas"].insert_many(docs_to_insert)
        inserted_count = len(res.inserted_ids)

    return {
        "insertados": inserted_count,
        "skus_no_encontrados": list(missing_skus),
        "total_recibidos": len(sales)
    }


@router.get("/by-sku/{sku_code}")
async def get_sales_by_sku(
    sku_code: str,
    limit: int = Query(365, le=1000),
    current_user: dict = Depends(get_current_user)
):
    """Consulta la serie de tiempo histórica de un producto específico."""
    db = get_database()
    prod = await db["productos"].find_one({"sku_code": sku_code})
    if not prod:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    cursor = db["historial_ventas"].find({"sku_id": prod["_id"]}).sort("fecha", -1).limit(limit)
    sales = []
    async for item in cursor:
        item["_id"] = str(item["_id"])
        item["sku_id"] = str(item["sku_id"])
        sales.append(item)

    return {
        "sku_code": sku_code,
        "registros": len(sales),
        "serie": sales
    }
