"""
Motor de Optimización Presupuestal para SAAML (RF04, RNF01).
Implementa un modelo de investigación de operaciones (Knapsack Multiobjetivo / Programación Entera Mixta - MILP)
utilizando PuLP para maximizar el beneficio y cobertura de demanda proyectada
respetando restricciones duras de presupuesto de capital, lotes mínimos (MOQ),
incrementos de empaque y capacidad volumétrica de almacén.
"""

from datetime import datetime, timedelta
import logging
import math
import time
from typing import Any, Dict, List, Optional
from bson import ObjectId
import pulp
from app.core.database import get_database
from app.models.schemas import SolverStatus
from app.services.ml_engine import ml_forecaster

logger = logging.getLogger("saaml.optimizer")


class BudgetKnapsackOptimizer:
    """
    Optimizador de compras basado en el problema de la mochila (Knapsack) con variables enteras y restricciones de lote.
    """

    async def optimize(
        self,
        ciclo_presupuestal_id: str,
        user_id: ObjectId,
        presupuesto_limite: Optional[float] = None,
        horizon_days: int = 14,
        considerar_volumen_almacen: bool = True,
        factor_seguridad: float = 1.0
    ) -> Dict[str, Any]:
        """
        Ejecuta la optimización presupuestal para el catálogo de productos activos (RF04).
        """
        t0 = time.perf_counter()
        db = get_database()

        # 1. Validar ciclo presupuestal
        try:
            ciclo_oid = ObjectId(ciclo_presupuestal_id)
        except Exception:
            raise ValueError(f"ID de ciclo inválido: {ciclo_presupuestal_id}")

        ciclo = await db["ciclos_presupuestales"].find_one({"_id": ciclo_oid})
        if not ciclo:
            raise ValueError(f"El ciclo presupuestal con ID '{ciclo_presupuestal_id}' no existe.")

        if ciclo.get("estado") != "ABIERTO":
            raise ValueError(f"El ciclo presupuestal '{ciclo.get('codigo_ciclo')}' no está ABIERTO.")

        # Determinar presupuesto disponible
        if presupuesto_limite is not None and presupuesto_limite > 0:
            presupuesto_disponible = float(presupuesto_limite)
        else:
            total_asignado = float(ciclo.get("presupuesto_total_asignado", 0.0))
            comprometido = float(ciclo.get("presupuesto_comprometido", 0.0))
            presupuesto_disponible = max(0.0, total_asignado - comprometido)

        if presupuesto_disponible <= 0:
            raise ValueError("El presupuesto disponible para este ciclo es $0 o insuficiente.")

        # 2. Consultar catálogo de productos activos
        cursor = db["productos"].find({"estado": "ACTIVO"})
        products = await cursor.to_list(length=500)
        if not products:
            raise ValueError("No se encontraron productos activos en el catálogo.")

        # 3. Consultar capacidad disponible en almacenes
        almacenes_map = {}
        async for alm in db["almacenes"].find({"estado": "ACTIVO"}):
            cap_total = float(alm.get("capacidad_total_volumen_cm3", 1e9))
            cap_ocupada = float(alm.get("capacidad_ocupada_actual_cm3", 0.0))
            almacenes_map[str(alm["_id"])] = max(0.0, cap_total - cap_ocupada)

        volumen_total_disponible = sum(almacenes_map.values()) if almacenes_map else 500_000_000.0

        # 4. Obtener proveedores para enriquecer información
        proveedores_map = {}
        async for prv in db["proveedores"].find({"estado": "ACTIVO"}):
            proveedores_map[str(prv["_id"])] = prv

        # 5. Analizar necesidades por SKU
        candidates = []
        total_deficit_global = 0.0

        for prod in products:
            sku_code = prod["sku_code"]
            sku_id = prod["_id"]

            # Obtener pronóstico de ML más reciente para este horizonte
            pred_doc = await db["predicciones_demanda"].find_one(
                {"sku_id": sku_id, "horizonte_dias": horizon_days},
                sort=[("fecha_generacion", -1)]
            )

            if not pred_doc:
                # Generar inferencia en tiempo real si aún no existe en BD
                try:
                    fc = await ml_forecaster.forecast_sku(sku_code=sku_code, horizon_days=horizon_days)
                    demanda_predicha = float(fc["demanda_total_proyectada"])
                except Exception as e:
                    logger.warning(f"No se pudo proyectar demanda para {sku_code}: {e}")
                    demanda_predicha = 0.0
            else:
                demanda_predicha = float(pred_doc.get("demanda_predicha", 0.0))

            stock_actual = int(prod.get("stock_actual", 0))
            stock_seguridad_base = int(prod.get("stock_seguridad", 0))
            stock_seguridad_efectivo = round(stock_seguridad_base * factor_seguridad)

            # Necesidad neta o déficit previsto
            deficit = max(0.0, float(demanda_predicha + stock_seguridad_efectivo - stock_actual))
            total_deficit_global += deficit

            if deficit <= 0:
                # El inventario actual cubre la demanda esperada + stock de seguridad
                continue

            costo = float(prod.get("costo_unitario", 0.0))
            precio = float(prod.get("precio_venta", 0.0))
            if costo <= 0:
                continue

            moq = max(1, int(prod.get("moq", 1)))
            lote = max(1, int(prod.get("incremento_lote", 1)))
            volumen_unit = float(prod.get("volumen_cm3", 1000.0))
            margen_unitario = max(0.01, precio - costo)

            # Mínimo de unidades si se pide (debe cumplir MOQ y ajustarse a lote)
            min_lotes = max(1, math.ceil(moq / lote))
            min_unidades = min_lotes * lote

            # Máximo aconsejable de unidades para no sobre-inventariar
            max_lotes = max(min_lotes, math.ceil(deficit / lote))
            max_unidades = max_lotes * lote

            prv_id_str = str(prod.get("proveedor_id"))
            prv_doc = proveedores_map.get(prv_id_str, {})
            calif_prv = float(prv_doc.get("calificacion_calidad", 5.0)) / 5.0

            candidates.append({
                "sku_id": sku_id,
                "sku_code": sku_code,
                "nombre": prod.get("nombre", sku_code),
                "categoria": prod.get("categoria", "General"),
                "proveedor_id": prod.get("proveedor_id"),
                "proveedor_nombre": prv_doc.get("nombre_empresa", "Proveedor General"),
                "lead_time_promedio_dias": int(prod.get("lead_time_promedio_dias", prv_doc.get("lead_time_promedio_dias", 7))),
                "almacen_id": prod.get("almacen_id"),
                "stock_actual": stock_actual,
                "stock_seguridad": stock_seguridad_efectivo,
                "demanda_predicha": demanda_predicha,
                "deficit": deficit,
                "costo_unitario": costo,
                "precio_venta": precio,
                "margen_unitario": margen_unitario,
                "moq": moq,
                "lote": lote,
                "min_lotes": min_lotes,
                "max_lotes": max_lotes,
                "min_unidades": min_unidades,
                "max_unidades": max_unidades,
                "volumen_cm3": volumen_unit,
                "peso_calidad_prv": calif_prv
            })

        # 6. Formular y resolver el modelo matemático MILP (Knapsack)
        items_recomendados = []
        solver_status_enum = SolverStatus.OPTIMAL

        if not candidates:
            # No hay necesidad de compra
            presupuesto_total_asignado = 0.0
            demanda_cubierta_pct = 100.0
        else:
            prob = pulp.LpProblem("SAAML_Budget_Optimization", pulp.LpMaximize)

            # Variables de decisión
            # y[i]: binaria (1 si se emite orden para el SKU i, 0 si no)
            # k[i]: entera (número de lotes a comprar)
            y = {}
            k = {}
            for idx, c in enumerate(candidates):
                y[idx] = pulp.LpVariable(f"y_{idx}", cat=pulp.LpBinary)
                k[idx] = pulp.LpVariable(f"k_{idx}", lowBound=0, upBound=c["max_lotes"], cat=pulp.LpInteger)

            # Restricciones:
            # 1. Vinculación lógica y MOQ
            for idx, c in enumerate(candidates):
                lote = c["lote"]
                prob += k[idx] * lote >= c["min_unidades"] * y[idx], f"MOQ_Min_{idx}"
                prob += k[idx] * lote <= c["max_unidades"] * y[idx], f"Cap_Max_{idx}"

            # 2. Restricción dura de presupuesto (Knapsack)
            prob += pulp.lpSum(
                candidates[idx]["costo_unitario"] * candidates[idx]["lote"] * k[idx]
                for idx in range(len(candidates))
            ) <= presupuesto_disponible, "Presupuesto_Maximo"

            # 3. Restricción de volumen de almacén (si está habilitada)
            if considerar_volumen_almacen and volumen_total_disponible > 0:
                prob += pulp.lpSum(
                    candidates[idx]["volumen_cm3"] * candidates[idx]["lote"] * k[idx]
                    for idx in range(len(candidates))
                ) <= volumen_total_disponible, "Capacidad_Almacen"

            # 4. Función Objetivo:
            # Maximizar el beneficio neto esperado de la inversión, ponderado por prioridad y calidad
            prob += pulp.lpSum(
                (candidates[idx]["margen_unitario"] * candidates[idx]["peso_calidad_prv"] + 0.05)
                * candidates[idx]["lote"] * k[idx]
                for idx in range(len(candidates))
            ), "Maximizar_Beneficio_Neto"

            # Resolver con solver CBC asegurando límite de 30 segundos (RNF01)
            solver = pulp.PULP_CBC_CMD(msg=0, timeLimit=30)
            prob.solve(solver)

            status_str = pulp.LpStatus[prob.status]
            if status_str == "Optimal":
                solver_status_enum = SolverStatus.OPTIMAL
            elif status_str == "Feasible":
                solver_status_enum = SolverStatus.FEASIBLE
            elif status_str == "Infeasible":
                solver_status_enum = SolverStatus.INFEASIBLE
            else:
                solver_status_enum = SolverStatus.ERROR

            # Extraer resultados
            total_unidades_cubiertas = 0.0
            for idx, c in enumerate(candidates):
                lotes_opt = int(round(k[idx].varValue or 0))
                qty_opt = lotes_opt * c["lote"]

                if qty_opt > 0:
                    subtotal = round(qty_opt * c["costo_unitario"], 2)
                    volumen_total = round(qty_opt * c["volumen_cm3"], 2)
                    cobertura_sku = round(min(100.0, (qty_opt / c["deficit"]) * 100.0), 1)
                    total_unidades_cubiertas += min(qty_opt, c["deficit"])

                    items_recomendados.append({
                        "sku_id": str(c["sku_id"]),
                        "sku_code": c["sku_code"],
                        "nombre_producto": c["nombre"],
                        "categoria": c["categoria"],
                        "proveedor_id": str(c["proveedor_id"]),
                        "proveedor_nombre": c["proveedor_nombre"],
                        "lead_time_promedio_dias": c["lead_time_promedio_dias"],
                        "almacen_id": str(c["almacen_id"]) if c["almacen_id"] else None,
                        "stock_actual": c["stock_actual"],
                        "demanda_proyectada": c["demanda_predicha"],
                        "stock_seguridad": c["stock_seguridad"],
                        "deficit_unidades": round(c["deficit"], 1),
                        "cantidad_sugerida_ml": qty_opt,
                        "costo_unitario": c["costo_unitario"],
                        "subtotal": subtotal,
                        "volumen_total_cm3": volumen_total,
                        "cobertura_deficit_porcentaje": cobertura_sku
                    })

            presupuesto_total_asignado = round(sum(i["subtotal"] for i in items_recomendados), 2)
            demanda_cubierta_pct = (
                round((total_unidades_cubiertas / total_deficit_global) * 100.0, 2)
                if total_deficit_global > 0 else 100.0
            )

        tiempo_ejecucion_ms = int((time.perf_counter() - t0) * 1000)
        presupuesto_remanente = max(0.0, round(presupuesto_disponible - presupuesto_total_asignado, 2))

        # 7. Persistir en la colección 'sesiones_optimizacion' (RF04, RNF01)
        sesion_doc = {
            "ciclo_presupuestal_id": ciclo_oid,
            "usuario_id": user_id,
            "fecha_ejecucion": datetime.utcnow(),
            "horizonte_dias": horizon_days,
            "presupuesto_disponible": presupuesto_disponible,
            "parametros_config": {
                "considerar_volumen_almacen": considerar_volumen_almacen,
                "factor_seguridad": factor_seguridad
            },
            "tiempo_ejecucion_ms": tiempo_ejecucion_ms,
            "solver_status": solver_status_enum.value,
            "demanda_total_cubierta_porcentaje": demanda_cubierta_pct,
            "presupuesto_total_asignado": presupuesto_total_asignado,
            "presupuesto_remanente": presupuesto_remanente,
            "skus_seleccionados_conteo": len(items_recomendados),
            "items_recomendados": items_recomendados
        }

        result = await db["sesiones_optimizacion"].insert_one(sesion_doc)
        sesion_doc["_id"] = str(result.inserted_id)
        sesion_doc["ciclo_presupuestal_id"] = str(ciclo_oid)
        sesion_doc["usuario_id"] = str(user_id)

        logger.info(
            f"Optimización completada en {tiempo_ejecucion_ms} ms. "
            f"SKUs: {len(items_recomendados)}, Presupuesto: ${presupuesto_total_asignado} / ${presupuesto_disponible} "
            f"(Cobertura: {demanda_cubierta_pct}%)"
        )

        return sesion_doc


# Singleton del optimizador
optimizer_engine = BudgetKnapsackOptimizer()
