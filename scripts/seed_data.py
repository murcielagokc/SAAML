"""
Script generador de datos semilla (Seed Data) para SAAML.
Crea usuarios, proveedores, almacenes, catálogo de productos,
1 año completo (365 días) de historial de ventas con variabilidad estocástica y estacionalidad,
historial de órdenes de compra pasadas y recepciones logísticas, ciclo presupuestal activo
y entrena de forma automática el modelo de Machine Learning (RF06 / RF02).

Uso:
    python scripts/seed_data.py
"""

import asyncio
from datetime import datetime, timedelta
import math
import random
import sys
from pathlib import Path

# Asegurar que el directorio raíz del proyecto esté en el PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bson import ObjectId
from app.core.config import settings
from app.core.database import close_mongo_connection, connect_to_mongo, get_database
from app.core.init_db import create_indexes
from app.core.security import get_password_hash
from app.services.ml_engine import ml_forecaster


async def seed_database():
    print("=" * 70)
    print("  SAAML - GENERADOR DE DATOS SEMILLA & PIPELINE DE ENTRENAMIENTO")
    print("=" * 70)
    print(f"[*] Conectando a MongoDB en: {settings.MONGODB_URI} -> BD: '{settings.MONGODB_DB_NAME}'")

    await connect_to_mongo()
    db = get_database()
    await create_indexes()

    # 1. Usuarios del Sistema
    print("\n[1/7] Sembrando usuarios de prueba con roles...")
    usuarios = [
        {
            "email": "admin@saaml.com",
            "password_hash": get_password_hash("Admin123*"),
            "nombre_completo": "Administrador General",
            "rol": "ADMIN",
            "estado": "ACTIVO",
            "intentos_fallidos": 0,
            "token_version": 1,
            "created_at": datetime.utcnow()
        },
        {
            "email": "gerente@saaml.com",
            "password_hash": get_password_hash("Gerente123*"),
            "nombre_completo": "Carlos Gerente de Compras",
            "rol": "GERENTE_COMPRAS",
            "estado": "ACTIVO",
            "intentos_fallidos": 0,
            "token_version": 1,
            "created_at": datetime.utcnow()
        }
    ]
    for u in usuarios:
        await db["usuarios"].update_one({"email": u["email"]}, {"$set": u}, upsert=True)
    admin_user = await db["usuarios"].find_one({"email": "admin@saaml.com"})
    print("    -> 2 usuarios listos (admin@saaml.com y gerente@saaml.com)")

    # 2. Almacén Central
    print("\n[2/7] Sembrando almacén central y capacidades...")
    almacen = {
        "codigo_almacen": "ALM-BOG-01",
        "nombre_almacen": "Centro de Distribución Central",
        "ubicacion": "Parque Logístico Calle 80",
        "capacidad_total_volumen_cm3": 500_000_000.0,  # 500 m3
        "capacidad_ocupada_actual_cm3": 85_000_000.0,
        "costo_mantenimiento_inventario_porcentaje": 0.02,
        "estado": "ACTIVO"
    }
    await db["almacenes"].update_one({"codigo_almacen": almacen["codigo_almacen"]}, {"$set": almacen}, upsert=True)
    almacen_doc = await db["almacenes"].find_one({"codigo_almacen": "ALM-BOG-01"})
    print(f"    -> Almacén '{almacen['nombre_almacen']}' configurado.")

    # 3. Proveedores
    print("\n[3/7] Sembrando proveedores comerciales...")
    proveedores_data = [
        {
            "codigo_proveedor": "PRV-TECH-01",
            "nombre_empresa": "TechSupply International",
            "contacto": {"nombre": "Laura Méndez", "email": "contacto@techsupply.com", "telefono": "+1-800-555-019"},
            "moneda": "USD",
            "condiciones_pago": "30_DIAS",
            "calificacion_calidad": 4.8,
            "variabilidad_lead_time_dias": 1.2,
            "lead_time_promedio_dias": 10,
            "estado": "ACTIVO",
            "created_at": datetime.utcnow()
        },
        {
            "codigo_proveedor": "PRV-INDUS-02",
            "nombre_empresa": "Manufacturas y Empaques S.A.",
            "contacto": {"nombre": "Roberto Gómez", "email": "ventas@manufacturas.com", "telefono": "+57-310-555-022"},
            "moneda": "USD",
            "condiciones_pago": "CONTADO",
            "calificacion_calidad": 4.5,
            "variabilidad_lead_time_dias": 0.8,
            "lead_time_promedio_dias": 5,
            "estado": "ACTIVO",
            "created_at": datetime.utcnow()
        }
    ]
    for p in proveedores_data:
        await db["proveedores"].update_one({"codigo_proveedor": p["codigo_proveedor"]}, {"$set": p}, upsert=True)

    prv1 = await db["proveedores"].find_one({"codigo_proveedor": "PRV-TECH-01"})
    prv2 = await db["proveedores"].find_one({"codigo_proveedor": "PRV-INDUS-02"})
    print(f"    -> {len(proveedores_data)} proveedores activos creados.")

    # 4. Catálogo de Productos (SKUs)
    print("\n[4/7] Sembrando catálogo maestro de productos...")
    productos_data = [
        {
            "sku_code": "SKU-AUR-001",
            "nombre": "Auriculares Inalámbricos Pro Noise Cancelling",
            "categoria": "Electrónica",
            "proveedor_id": prv1["_id"],
            "almacen_id": almacen_doc["_id"],
            "costo_unitario": 35.0,
            "precio_venta": 79.9,
            "stock_actual": 45,
            "stock_seguridad": 25,
            "moq": 10,
            "incremento_lote": 5,
            "volumen_cm3": 1200.0,
            "lead_time_promedio_dias": 10,
            "estado": "ACTIVO",
            "audit": {"created_at": datetime.utcnow(), "updated_at": datetime.utcnow()}
        },
        {
            "sku_code": "SKU-MOU-002",
            "nombre": "Mouse Ergonómico Óptico Bluetooth",
            "categoria": "Electrónica",
            "proveedor_id": prv1["_id"],
            "almacen_id": almacen_doc["_id"],
            "costo_unitario": 12.5,
            "precio_venta": 29.9,
            "stock_actual": 80,
            "stock_seguridad": 30,
            "moq": 20,
            "incremento_lote": 10,
            "volumen_cm3": 800.0,
            "lead_time_promedio_dias": 10,
            "estado": "ACTIVO",
            "audit": {"created_at": datetime.utcnow(), "updated_at": datetime.utcnow()}
        },
        {
            "sku_code": "SKU-TEC-003",
            "nombre": "Teclado Mecánico RGB Switch Red",
            "categoria": "Electrónica",
            "proveedor_id": prv1["_id"],
            "almacen_id": almacen_doc["_id"],
            "costo_unitario": 42.0,
            "precio_venta": 89.0,
            "stock_actual": 15,
            "stock_seguridad": 15,
            "moq": 10,
            "incremento_lote": 5,
            "volumen_cm3": 2500.0,
            "lead_time_promedio_dias": 12,
            "estado": "ACTIVO",
            "audit": {"created_at": datetime.utcnow(), "updated_at": datetime.utcnow()}
        },
        {
            "sku_code": "SKU-HUB-004",
            "nombre": "Hub USB-C 7 en 1 Multifunción 4K HDMI",
            "categoria": "Accesorios",
            "proveedor_id": prv1["_id"],
            "almacen_id": almacen_doc["_id"],
            "costo_unitario": 18.0,
            "precio_venta": 45.0,
            "stock_actual": 12,
            "stock_seguridad": 20,
            "moq": 15,
            "incremento_lote": 5,
            "volumen_cm3": 500.0,
            "lead_time_promedio_dias": 8,
            "estado": "ACTIVO",
            "audit": {"created_at": datetime.utcnow(), "updated_at": datetime.utcnow()}
        },
        {
            "sku_code": "SKU-SUP-005",
            "nombre": "Soporte de Aluminio Ajustable para Laptop",
            "categoria": "Oficina",
            "proveedor_id": prv2["_id"],
            "almacen_id": almacen_doc["_id"],
            "costo_unitario": 14.0,
            "precio_venta": 34.5,
            "stock_actual": 60,
            "stock_seguridad": 20,
            "moq": 12,
            "incremento_lote": 6,
            "volumen_cm3": 1800.0,
            "lead_time_promedio_dias": 5,
            "estado": "ACTIVO",
            "audit": {"created_at": datetime.utcnow(), "updated_at": datetime.utcnow()}
        }
    ]

    for prod in productos_data:
        await db["productos"].update_one({"sku_code": prod["sku_code"]}, {"$set": prod}, upsert=True)

    all_products = await db["productos"].find().to_list(length=100)
    print(f"    -> {len(all_products)} productos en catálogo.")

    # 5. Generar Historial de Ventas Sintético (1 Año Completo = 365 días) con Variabilidad Dinámica
    print("\n[5/7] Generando 365 días (1 año) de historial de ventas diario con alta variabilidad...")
    now = datetime.utcnow()
    await db["historial_ventas"].delete_many({})

    batch_ventas = []
    base_demands = {
        "SKU-AUR-001": 9.0,
        "SKU-MOU-002": 16.0,
        "SKU-TEC-003": 6.0,
        "SKU-HUB-004": 13.0,
        "SKU-SUP-005": 8.0
    }

    random.seed(42)  # Semilla fija para reproducibilidad

    for day_offset in range(365, 0, -1):
        fecha = (now - timedelta(days=day_offset)).replace(hour=12, minute=0, second=0, microsecond=0)
        weekday = fecha.weekday()  # 0=Lunes, 4=Viernes, 5=Sábado, 6=Domingo
        dia_del_mes = fecha.day
        mes = fecha.month

        # 1. Variabilidad por día de semana (Picos en Viernes y Sábado)
        if weekday in [4, 5]:
            factor_semanal = random.uniform(1.35, 1.65)
        elif weekday == 6:
            factor_semanal = random.uniform(0.75, 0.95)
        elif weekday in [0, 1]:
            factor_semanal = random.uniform(0.85, 1.05)
        else:  # Miércoles, Jueves
            factor_semanal = random.uniform(1.00, 1.20)

        # 2. Efecto quincena y fin de mes (días de pago)
        factor_quincena = 1.0
        if dia_del_mes in [14, 15, 16, 29, 30, 31]:
            factor_quincena = random.uniform(1.20, 1.40)

        # 3. Estacionalidad mensual anual (Black Friday en Noviembre, Navidad en Diciembre)
        factor_mes = 1.0
        if mes == 11:  # Noviembre
            factor_mes = random.uniform(1.30, 1.55)
        elif mes == 12:  # Diciembre
            factor_mes = random.uniform(1.45, 1.75)
        elif mes == 1:  # Cuesta de Enero
            factor_mes = random.uniform(0.70, 0.85)

        # 4. Tendencia anual (ligero crecimiento del 10% hacia fechas recientes)
        progreso_anual = (365 - day_offset) / 365.0
        factor_tendencia = 1.0 + (0.10 * progreso_anual)

        for prod in all_products:
            base = base_demands.get(prod["sku_code"], 10.0)

            # Ruido estocástico Gaussiano
            ruido = random.gauss(mu=1.0, sigma=0.18)

            # Probabilidad de descuento / promoción aleatoria (15% de los días)
            tiene_descuento = random.random() < 0.15
            pct_descuento = random.choice([0.05, 0.10, 0.15, 0.20]) if tiene_descuento else 0.0
            impulso_descuento = 1.0 + (pct_descuento * 1.8)

            # Probabilidad de quiebre de stock (stockout): 2% de los días
            stockout = random.random() < 0.02

            if stockout:
                unidades = 0
            else:
                demanda_calculada = (
                    base
                    * factor_semanal
                    * factor_quincena
                    * factor_mes
                    * factor_tendencia
                    * impulso_descuento
                    * ruido
                )
                unidades = max(1, int(round(demanda_calculada)))

            batch_ventas.append({
                "sku_id": prod["_id"],
                "fecha": fecha,
                "cantidad_vendida": unidades,
                "precio_unitario_aplicado": round(prod["precio_venta"] * (1.0 - pct_descuento), 2),
                "descuento_porcentaje": pct_descuento,
                "stockout_flag": stockout,
                "canal_venta": random.choice(["RETAIL", "ONLINE", "B2B"]),
                "almacen_id": almacen_doc["_id"]
            })

    if batch_ventas:
        await db["historial_ventas"].insert_many(batch_ventas)
    print(f"    -> {len(batch_ventas)} registros históricos de ventas sembrados (365 días x {len(all_products)} SKUs).")

    # 6. Historial de Compras Simuladas y Recepciones Logísticas Pasadas (Últimos 12 meses)
    print("\n[6/7] Sembrando historial de compras y recepciones logísticas de los últimos 12 meses...")
    await db["ordenes_compra"].delete_many({})
    await db["recepciones_logistica"].delete_many({})

    hist_orders = []
    hist_recepciones = []

    for month_offset in range(12, 0, -1):
        order_date = (now - timedelta(days=month_offset * 30 + 15)).replace(hour=10, minute=0, second=0, microsecond=0)
        year_order = order_date.year
        seq_num = 13 - month_offset

        for idx, prv in enumerate([prv1, prv2], start=1):
            prv_products = [p for p in all_products if str(p["proveedor_id"]) == str(prv["_id"])]
            if not prv_products:
                continue

            order_items = []
            costo_total = 0.0
            lead_time = int(prv.get("lead_time_promedio_dias", 7))
            fecha_entrega_prometida = order_date + timedelta(days=lead_time)

            # Desviación realista de entrega (-1 a +2 días)
            dias_desv = random.choice([0, 0, 1, -1, 2])
            fecha_recepcion_real = fecha_entrega_prometida + timedelta(days=dias_desv)

            order_id = ObjectId()

            for p in prv_products:
                qty = random.randint(30, 90)
                subtot = round(qty * p["costo_unitario"], 2)
                costo_total += subtot

                order_items.append({
                    "sku_id": p["_id"],
                    "sku_code": p["sku_code"],
                    "nombre_producto": p["nombre"],
                    "cantidad_sugerida_ml": qty,
                    "cantidad_final_aprobada": qty,
                    "costo_unitario": p["costo_unitario"],
                    "subtotal": subtot,
                    "volumen_total_cm3": round(qty * p["volumen_cm3"], 2)
                })

                # Generar recepción logística asociada
                hist_recepciones.append({
                    "orden_compra_id": order_id,
                    "proveedor_id": prv["_id"],
                    "sku_id": p["_id"],
                    "cantidad_prometida": qty,
                    "cantidad_recibida_real": qty,
                    "fecha_entrega_prometida": fecha_entrega_prometida,
                    "fecha_recepcion_real": fecha_recepcion_real,
                    "dias_desviacion": dias_desv,
                    "estado_calidad": "CONFORME",
                    "created_at": fecha_recepcion_real
                })

            codigo_orden = f"PO-{year_order}-{seq_num * 2 + idx:04d}"
            hist_orders.append({
                "_id": order_id,
                "codigo_orden": codigo_orden,
                "sesion_optimizacion_id": None,
                "ciclo_presupuestal_id": None,
                "proveedor_id": prv["_id"],
                "almacen_id": almacen_doc["_id"],
                "fecha_generacion": order_date,
                "fecha_entrega_estimada": fecha_entrega_prometida,
                "costo_total_orden": round(costo_total, 2),
                "estado": "RECIBIDA_TOTAL",
                "nivel_confianza_ml_promedio": 0.88,
                "items": order_items,
                "audit": {
                    "generado_por": admin_user["_id"],
                    "aprobado_por": admin_user["_id"],
                    "fecha_aprobacion": order_date + timedelta(hours=2)
                }
            })

    if hist_orders:
        await db["ordenes_compra"].insert_many(hist_orders)
    if hist_recepciones:
        await db["recepciones_logistica"].insert_many(hist_recepciones)
    print(f"    -> {len(hist_orders)} órdenes históricas 'RECIBIDA_TOTAL' creadas con {len(hist_recepciones)} recepciones logísticas.")

    # 7. Ciclo Presupuestal Actual Activo
    print("\n[7/7] Configurando ciclo presupuestal activo...")
    ciclo = {
        "codigo_ciclo": "CP-2026-M10",
        "periodo": "OCTUBRE_2026",
        "fecha_inicio": datetime(2026, 10, 1),
        "fecha_fin": datetime(2026, 10, 31),
        "presupuesto_total_asignado": 25_000.0,
        "presupuesto_comprometido": 0.0,
        "presupuesto_consumido_real": 0.0,
        "estado": "ABIERTO",
        "created_by": admin_user["_id"]
    }
    await db["ciclos_presupuestales"].update_one({"codigo_ciclo": ciclo["codigo_ciclo"]}, {"$set": ciclo}, upsert=True)
    print(f"    -> Ciclo '{ciclo['codigo_ciclo']}' abierto ($25,000 USD).")

    # 8. Entrenar Modelo de Machine Learning y Pre-calcular Pronósticos
    print("\n" + "=" * 70)
    print("  EJECUTANDO PIPELINE DE MACHINE LEARNING (RF06 / RF02)...")
    print("=" * 70)
    try:
        resultado_ml = await ml_forecaster.train_and_evaluate()
        print(f"[+] Modelo entrenado con éxito.")
        print(f"    - Versión: {resultado_ml['version']}")
        print(f"    - SKUs entrenados: {resultado_ml['skus_entrenados_conteo']}")
        print(f"    - Métricas promedio: {resultado_ml['metricas']}")
        print(f"    - Artefacto Joblib guardado en: {resultado_ml['artefacto_guardado_en']}")

        print("\n[*] Pre-calculando predicciones de demanda a 14 días para todo el catálogo...")
        for p in all_products:
            await ml_forecaster.forecast_sku(sku_code=p["sku_code"], horizon_days=14)
        print("[+] Predicciones persistidas en MongoDB Atlas (Colección 'predicciones_demanda').")

    except Exception as e:
        print(f"[-] Advertencia durante el entrenamiento automático de ML: {e}")

    print("\n" + "=" * 70)
    print("[OK] SEED Y ENTRENAMIENTO COMPLETADOS CON ÉXITO")
    print("=" * 70)
    await close_mongo_connection()


if __name__ == "__main__":
    asyncio.run(seed_database())
