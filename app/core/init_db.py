import logging
from pymongo import ASCENDING, DESCENDING, IndexModel
from app.core.database import get_database

logger = logging.getLogger("saaml.init_db")


async def create_indexes():
    """
    Crea los índices estratégicos en MongoDB para garantizar latencias < 30s (RNF01)
    y soporte de consultas de series temporales de ML.
    """
    from app.core.database import db_manager

    if not db_manager.is_connected:
        logger.info("MongoDB no está conectado aún. La creación de índices se ejecutará una vez se configure MONGODB_URI.")
        return

    try:
        db = get_database()
        logger.info("Iniciando verificación y creación de índices en MongoDB...")

        # 1. Usuarios
        await db["usuarios"].create_indexes([
            IndexModel([("email", ASCENDING)], unique=True, name="idx_usuarios_email_unique")
        ])

        # 2. Proveedores
        await db["proveedores"].create_indexes([
            IndexModel([("codigo_proveedor", ASCENDING)], unique=True, name="idx_prov_codigo_unique"),
            IndexModel([("estado", ASCENDING)], name="idx_prov_estado")
        ])

        # 3. Almacenes
        await db["almacenes"].create_indexes([
            IndexModel([("codigo_almacen", ASCENDING)], unique=True, name="idx_almacen_codigo_unique")
        ])

        # 4. Productos
        await db["productos"].create_indexes([
            IndexModel([("sku_code", ASCENDING)], unique=True, name="idx_prod_sku_unique"),
            IndexModel([("categoria", ASCENDING)], name="idx_prod_categoria"),
            IndexModel([("proveedor_id", ASCENDING)], name="idx_prod_proveedor"),
            IndexModel([("estado", ASCENDING)], name="idx_prod_estado")
        ])

        # 5. Historial de Ventas (Compuesto para series temporales por SKU)
        await db["historial_ventas"].create_indexes([
            IndexModel([("sku_id", ASCENDING), ("fecha", DESCENDING)], name="idx_ventas_sku_fecha"),
            IndexModel([("fecha", DESCENDING)], name="idx_ventas_fecha")
        ])

        # 6. Eventos Calendario
        await db["eventos_calendario"].create_indexes([
            IndexModel([("fecha_inicio", ASCENDING), ("fecha_fin", ASCENDING)], name="idx_eventos_fechas")
        ])

        # 7. Ciclos Presupuestales
        await db["ciclos_presupuestales"].create_indexes([
            IndexModel([("codigo_ciclo", ASCENDING)], unique=True, name="idx_ciclo_codigo_unique"),
            IndexModel([("estado", ASCENDING)], name="idx_ciclo_estado")
        ])

        # 8. Modelos ML
        await db["modelos_ml"].create_indexes([
            IndexModel([("version_modelo", ASCENDING)], unique=True, name="idx_modelo_version_unique"),
            IndexModel([("estado_despliegue", ASCENDING)], name="idx_modelo_estado")
        ])

        # 9. Predicciones Demanda
        await db["predicciones_demanda"].create_indexes([
            IndexModel([("sku_id", ASCENDING), ("fecha_inicio_proyeccion", ASCENDING)], name="idx_pred_sku_periodo"),
            IndexModel([("fecha_generacion", DESCENDING)], name="idx_pred_fecha_gen")
        ])

        # 10. Sesiones de Optimización
        await db["sesiones_optimizacion"].create_indexes([
            IndexModel([("ciclo_presupuestal_id", ASCENDING)], name="idx_opt_ciclo"),
            IndexModel([("fecha_ejecucion", DESCENDING)], name="idx_opt_fecha")
        ])

        # 11. Ordenes de Compra
        await db["ordenes_compra"].create_indexes([
            IndexModel([("codigo_orden", ASCENDING)], unique=True, name="idx_orden_codigo_unique"),
            IndexModel([("proveedor_id", ASCENDING)], name="idx_orden_proveedor"),
            IndexModel([("estado", ASCENDING)], name="idx_orden_estado"),
            IndexModel([("fecha_generacion", DESCENDING)], name="idx_orden_fecha_gen")
        ])

        # 12. Recepciones Logísticas
        await db["recepciones_logistica"].create_indexes([
            IndexModel([("orden_compra_id", ASCENDING)], name="idx_recep_orden"),
            IndexModel([("sku_id", ASCENDING)], name="idx_recep_sku")
        ])

        # 13. Logs de Seguridad y Auditoría
        await db["logs_seguridad_auditoria"].create_indexes([
            IndexModel([("timestamp", DESCENDING)], name="idx_logs_timestamp"),
            IndexModel([("accion", ASCENDING)], name="idx_logs_accion"),
            IndexModel([("usuario_id", ASCENDING)], name="idx_logs_usuario")
        ])

        logger.info("Índices de MongoDB creados y verificados con éxito.")
    except Exception as e:
        logger.warning(f"No se pudieron crear índices en MongoDB (modo offline o BD no iniciada): {e}")
