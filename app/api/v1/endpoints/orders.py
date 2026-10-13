from datetime import datetime, timedelta
from typing import Dict, List, Optional
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from app.api.v1.endpoints.auth import get_current_user
from app.core.database import get_database
from app.models.schemas import EstadoOrdenCompra

router = APIRouter(prefix="/orders", tags=["Órdenes de Compra y Recomendaciones (RF05)"])


class ItemQuantityAdjustment(BaseModel):
    sku_code: str
    cantidad_final_aprobada: int = Field(ge=0, description="Cantidad final aprobada por el gerente")


class AdjustOrderItemsRequest(BaseModel):
    items: List[ItemQuantityAdjustment]


@router.post("/generate-from-session/{session_id}", status_code=status.HTTP_201_CREATED)
async def generate_orders_from_session(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Genera las órdenes de compra propuestas en estado 'BORRADOR_PROPUESTA' agrupadas por proveedor,
    a partir del resultado del motor de optimización Knapsack (RF05).
    Actualiza el presupuesto comprometido en el ciclo correspondiente.
    """
    db = get_database()
    try:
        s_oid = ObjectId(session_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID de sesión inválido")

    session = await db["sesiones_optimizacion"].find_one({"_id": s_oid})
    if not session:
        raise HTTPException(status_code=404, detail="Sesión de optimización no encontrada")

    items_recomendados = session.get("items_recomendados", [])
    if not items_recomendados:
        raise HTTPException(
            status_code=400,
            detail="La sesión de optimización no generó recomendaciones de compra para ningún SKU."
        )

    # Verificar si ya se habían generado órdenes para esta sesión
    existing_orders = await db["ordenes_compra"].find({"sesion_optimizacion_id": s_oid}).to_list(length=100)
    if existing_orders:
        raise HTTPException(
            status_code=400,
            detail=f"Ya existen {len(existing_orders)} órdenes de compra generadas para esta sesión de optimización."
        )

    ciclo_id = session["ciclo_presupuestal_id"]
    ciclo = await db["ciclos_presupuestales"].find_one({"_id": ciclo_id})
    if not ciclo:
        raise HTTPException(status_code=404, detail="Ciclo presupuestal vinculado no encontrado")

    # Agrupar items por proveedor_id
    items_by_provider = {}
    for item in items_recomendados:
        prv_id = item["proveedor_id"]
        if prv_id not in items_by_provider:
            items_by_provider[prv_id] = []
        items_by_provider[prv_id].append(item)

    year = datetime.utcnow().year
    created_orders = []
    total_monto_generado = 0.0

    # Obtener el correlativo más alto existente para el año actual
    last_orders = await db["ordenes_compra"].find(
        {"codigo_orden": {"$regex": f"^PO-{year}-"}},
        {"codigo_orden": 1}
    ).sort("codigo_orden", -1).to_list(length=1)

    if last_orders:
        try:
            current_seq = int(last_orders[0]["codigo_orden"].split("-")[-1])
        except Exception:
            current_seq = await db["ordenes_compra"].count_documents({})
    else:
        current_seq = 0

    for prv_id_str, prov_items in items_by_provider.items():
        prv_oid = ObjectId(prv_id_str)
        prv_doc = await db["proveedores"].find_one({"_id": prv_oid})
        lead_time = int(prv_doc.get("lead_time_promedio_dias", 7)) if prv_doc else 7

        current_seq += 1
        codigo_orden = f"PO-{year}-{current_seq:04d}"
        while await db["ordenes_compra"].find_one({"codigo_orden": codigo_orden}):
            current_seq += 1
            codigo_orden = f"PO-{year}-{current_seq:04d}"


        costo_total_orden = 0.0
        order_items_doc = []

        for pi in prov_items:
            subtotal = round(pi["cantidad_sugerida_ml"] * pi["costo_unitario"], 2)
            costo_total_orden += subtotal
            order_items_doc.append({
                "sku_id": ObjectId(pi["sku_id"]),
                "sku_code": pi["sku_code"],
                "nombre_producto": pi["nombre_producto"],
                "cantidad_sugerida_ml": pi["cantidad_sugerida_ml"],
                "cantidad_final_aprobada": pi["cantidad_sugerida_ml"],
                "costo_unitario": pi["costo_unitario"],
                "subtotal": subtotal,
                "volumen_total_cm3": pi.get("volumen_total_cm3", 0.0)
            })

        costo_total_orden = round(costo_total_orden, 2)
        total_monto_generado += costo_total_orden

        almacen_id_obj = ObjectId(prov_items[0]["almacen_id"]) if prov_items[0].get("almacen_id") else None

        order_doc = {
            "codigo_orden": codigo_orden,
            "sesion_optimizacion_id": s_oid,
            "ciclo_presupuestal_id": ciclo_id,
            "proveedor_id": prv_oid,
            "almacen_id": almacen_id_obj,
            "fecha_generacion": datetime.utcnow(),
            "fecha_entrega_estimada": datetime.utcnow() + timedelta(days=lead_time),
            "costo_total_orden": costo_total_orden,
            "estado": EstadoOrdenCompra.BORRADOR_PROPUESTA.value,
            "nivel_confianza_ml_promedio": 0.85,
            "items": order_items_doc,
            "audit": {
                "generado_por": current_user["_id"],
                "aprobado_por": None,
                "fecha_aprobacion": None
            }
        }

        res = await db["ordenes_compra"].insert_one(order_doc)
        order_doc["_id"] = str(res.inserted_id)
        order_doc["sesion_optimizacion_id"] = str(s_oid)
        order_doc["ciclo_presupuestal_id"] = str(ciclo_id)
        order_doc["proveedor_id"] = str(prv_oid)
        if almacen_id_obj:
            order_doc["almacen_id"] = str(almacen_id_obj)
        order_doc["audit"]["generado_por"] = str(current_user["_id"])

        for it in order_doc["items"]:
            it["sku_id"] = str(it["sku_id"])

        created_orders.append(order_doc)

    # Actualizar presupuesto comprometido en el ciclo presupuestal
    nuevo_comprometido = round(float(ciclo.get("presupuesto_comprometido", 0.0)) + total_monto_generado, 2)
    await db["ciclos_presupuestales"].update_one(
        {"_id": ciclo_id},
        {"$set": {"presupuesto_comprometido": nuevo_comprometido}}
    )

    return {
        "message": f"Se generaron {len(created_orders)} órdenes de compra en estado BORRADOR_PROPUESTA exitosamente.",
        "total_ordenes": len(created_orders),
        "monto_total_comprometido": round(total_monto_generado, 2),
        "ordenes": created_orders
    }


@router.get("/")
async def list_orders(
    estado: Optional[str] = Query(None, description="Filtrar por estado: BORRADOR_PROPUESTA, APROBADA, etc."),
    proveedor_id: Optional[str] = Query(None),
    ciclo_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user)
):
    """
    Lista las órdenes de compra emitidas con soporte de filtros (RF05).
    """
    db = get_database()
    query = {}
    if estado:
        query["estado"] = estado
    if proveedor_id:
        try:
            query["proveedor_id"] = ObjectId(proveedor_id)
        except Exception:
            raise HTTPException(status_code=400, detail="ID de proveedor inválido")
    if ciclo_id:
        try:
            query["ciclo_presupuestal_id"] = ObjectId(ciclo_id)
        except Exception:
            raise HTTPException(status_code=400, detail="ID de ciclo inválido")

    cursor = db["ordenes_compra"].find(query).sort("fecha_generacion", -1).skip(skip).limit(limit)
    orders = []

    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        doc["ciclo_presupuestal_id"] = str(doc["ciclo_presupuestal_id"])
        doc["proveedor_id"] = str(doc["proveedor_id"])
        if doc.get("sesion_optimizacion_id"):
            doc["sesion_optimizacion_id"] = str(doc["sesion_optimizacion_id"])
        if doc.get("almacen_id"):
            doc["almacen_id"] = str(doc["almacen_id"])
        if "audit" in doc and doc["audit"].get("generado_por"):
            doc["audit"]["generado_por"] = str(doc["audit"]["generado_por"])
        if "audit" in doc and doc["audit"].get("aprobado_por"):
            doc["audit"]["aprobado_por"] = str(doc["audit"]["aprobado_por"])

        for it in doc.get("items", []):
            if "sku_id" in it:
                it["sku_id"] = str(it["sku_id"])

        orders.append(doc)

    total = await db["ordenes_compra"].count_documents(query)
    return {"total": total, "items": orders}


@router.get("/{order_id}")
async def get_order_by_id(
    order_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Consulta los detalles completos de una orden de compra, incluyendo datos del proveedor asociado.
    """
    db = get_database()
    try:
        oid = ObjectId(order_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID de orden inválido")

    order = await db["ordenes_compra"].find_one({"_id": oid})
    if not order:
        raise HTTPException(status_code=404, detail="Orden de compra no encontrada")

    proveedor = await db["proveedores"].find_one({"_id": order["proveedor_id"]})

    order["_id"] = str(order["_id"])
    order["ciclo_presupuestal_id"] = str(order["ciclo_presupuestal_id"])
    order["proveedor_id"] = str(order["proveedor_id"])
    if order.get("sesion_optimizacion_id"):
        order["sesion_optimizacion_id"] = str(order["sesion_optimizacion_id"])
    if order.get("almacen_id"):
        order["almacen_id"] = str(order["almacen_id"])
    if "audit" in order and order["audit"].get("generado_por"):
        order["audit"]["generado_por"] = str(order["audit"]["generado_por"])
    if "audit" in order and order["audit"].get("aprobado_por"):
        order["audit"]["aprobado_por"] = str(order["audit"]["aprobado_por"])

    for it in order.get("items", []):
        it["sku_id"] = str(it["sku_id"])

    if proveedor:
        order["proveedor_info"] = {
            "nombre_empresa": proveedor.get("nombre_empresa"),
            "codigo_proveedor": proveedor.get("codigo_proveedor"),
            "contacto": proveedor.get("contacto"),
            "condiciones_pago": proveedor.get("condiciones_pago")
        }

    return order


@router.patch("/{order_id}/items")
async def adjust_order_items(
    order_id: str,
    adjust_in: AdjustOrderItemsRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Permite al gerente ajustar manualmente las cantidades aprobadas de los productos
    en una orden en estado 'BORRADOR_PROPUESTA' antes de su confirmación (RF05).
    Recalcula subtotales, costo total y ajusta el presupuesto comprometido.
    """
    db = get_database()
    try:
        oid = ObjectId(order_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID de orden inválido")

    order = await db["ordenes_compra"].find_one({"_id": oid})
    if not order:
        raise HTTPException(status_code=404, detail="Orden no encontrada")

    if order.get("estado") != EstadoOrdenCompra.BORRADOR_PROPUESTA.value:
        raise HTTPException(status_code=400, detail="Solo se pueden ajustar cantidades en órdenes en estado BORRADOR_PROPUESTA")

    adj_map = {item.sku_code: item.cantidad_final_aprobada for item in adjust_in.items}
    items = order.get("items", [])
    nuevo_costo_total = 0.0

    for it in items:
        sku = it["sku_code"]
        if sku in adj_map:
            it["cantidad_final_aprobada"] = adj_map[sku]
            it["subtotal"] = round(adj_map[sku] * it["costo_unitario"], 2)
        nuevo_costo_total += it["subtotal"]

    nuevo_costo_total = round(nuevo_costo_total, 2)
    diferencia = round(nuevo_costo_total - float(order.get("costo_total_orden", 0.0)), 2)

    # Actualizar orden
    await db["ordenes_compra"].update_one(
        {"_id": oid},
        {"$set": {"items": items, "costo_total_orden": nuevo_costo_total}}
    )

    # Ajustar presupuesto comprometido en el ciclo
    if diferencia != 0.0:
        await db["ciclos_presupuestales"].update_one(
            {"_id": order["ciclo_presupuestal_id"]},
            {"$inc": {"presupuesto_comprometido": diferencia}}
        )

    return {
        "message": "Cantidades ajustadas exitosamente",
        "codigo_orden": order["codigo_orden"],
        "costo_total_anterior": order.get("costo_total_orden"),
        "nuevo_costo_total": nuevo_costo_total,
        "diferencia_presupuesto": diferencia
    }


@router.patch("/{order_id}/approve")
async def approve_order(
    order_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Aprueba formalmente la orden de compra propuesta (cambio a estado 'APROBADA'),
    sellando la auditoría de aprobación con el usuario y marca temporal (RF05).
    """
    db = get_database()
    try:
        oid = ObjectId(order_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID de orden inválido")

    order = await db["ordenes_compra"].find_one({"_id": oid})
    if not order:
        raise HTTPException(status_code=404, detail="Orden de compra no encontrada")

    if order.get("estado") != EstadoOrdenCompra.BORRADOR_PROPUESTA.value:
        raise HTTPException(status_code=400, detail=f"No se puede aprobar una orden en estado {order.get('estado')}")

    now = datetime.utcnow()
    await db["ordenes_compra"].update_one(
        {"_id": oid},
        {
            "$set": {
                "estado": EstadoOrdenCompra.APROBADA.value,
                "audit.aprobado_por": current_user["_id"],
                "audit.fecha_aprobacion": now
            }
        }
    )

    return {
        "message": "Orden de compra aprobada exitosamente",
        "codigo_orden": order["codigo_orden"],
        "estado": EstadoOrdenCompra.APROBADA.value,
        "aprobado_por": str(current_user["_id"]),
        "fecha_aprobacion": now
    }


@router.patch("/{order_id}/cancel")
async def cancel_order(
    order_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Cancela una orden de compra y libera el presupuesto comprometido correspondiente en el ciclo.
    """
    db = get_database()
    try:
        oid = ObjectId(order_id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID de orden inválido")

    order = await db["ordenes_compra"].find_one({"_id": oid})
    if not order:
        raise HTTPException(status_code=404, detail="Orden no encontrada")

    if order.get("estado") == EstadoOrdenCompra.CANCELADA.value:
        raise HTTPException(status_code=400, detail="La orden ya se encuentra cancelada")

    costo_a_liberar = float(order.get("costo_total_orden", 0.0))

    await db["ordenes_compra"].update_one(
        {"_id": oid},
        {"$set": {"estado": EstadoOrdenCompra.CANCELADA.value}}
    )

    # Liberar presupuesto comprometido
    if costo_a_liberar > 0:
        await db["ciclos_presupuestales"].update_one(
            {"_id": order["ciclo_presupuestal_id"]},
            {"$inc": {"presupuesto_comprometido": -costo_a_liberar}}
        )

    return {
        "message": "Orden cancelada exitosamente y presupuesto liberado",
        "codigo_orden": order["codigo_orden"],
        "presupuesto_liberado": costo_a_liberar
    }
