# **Arquitectura de Base de Datos \- Sistema de Aprovisionamiento Autónomo**

Este documento detalla el esquema NoSQL (Documental) diseñado para el sistema. Se divide en el alcance principal (necesario para el prototipo) y el alcance de escalabilidad (fases futuras).

## **Fase 1: Alcance Principal del Prototipo**

### **1\. Usuarios (Seguridad y Auditoría)**

* `_id`: ObjectID  
* `email`: String (Único)  
* `password_hash`: String  
* `rol`: String (Enum: ADMIN, GERENTE\_COMPRAS, SISTEMA\_ML)  
* `estado`: String (Enum: ACTIVO, SUSPENDIDO)  
* `ultimo_acceso`: Date (ISO)

### **2\. Productos (Catálogo Master)**

* `_id`: ObjectID  
* `sku_code`: String (Indexado, Único)  
* `nombre`: String  
* `categoria`: String  
* `costo_unitario`: Decimal128  
* `precio_venta`: Decimal128  
* `stock_actual`: Integer  
* `stock_seguridad`: Integer  
* `moq`: Integer (Minimum Order Quantity)  
* `volumen_cm3`: Double  
* `lead_time_promedio_dias`: Integer  
* `estado`: String (Enum: ACTIVO, DISCONTINUADO)  
* `audit`: Objeto { created\_at: Date, updated\_at: Date }

### **3\. Proveedores (Riesgo y Desempeño)**

* `_id`: ObjectID  
* `nombre_empresa`: String  
* `moneda`: String  
* `condiciones_pago`: String  
* `calificacion_calidad`: Double (1.0 \- 5.0)  
* `variabilidad_lead_time_dias`: Double (Desviación estándar)  
* `estado`: String (Enum: ACTIVO, INACTIVO)

### **4\. Historial\_Ventas (Motor de Machine Learning)**

* `_id`: ObjectID  
* `sku_id`: ObjectID (Ref: Productos)  
* `fecha`: Date (ISO, indexado)  
* `cantidad_vendida`: Integer  
* `precio_unitario_aplicado`: Decimal128  
* `descuento_porcentaje`: Double  
* `stockout_flag`: Boolean  
* `canal_venta`: String

### **5\. Eventos\_Calendario (Variables Exógenas para ML)**

* `_id`: ObjectID  
* `nombre_evento`: String  
* `tipo_evento`: String (Enum: FERIADO, CAMPAÑA, DESASTRE)  
* `fecha_inicio`: Date (ISO)  
* `fecha_fin`: Date (ISO)  
* `multiplicador_esperado_demanda`: Double

### **6\. Ciclos\_Presupuestales (Restricciones del Negocio)**

* `_id`: ObjectID  
* `periodo`: String  
* `presupuesto_total_asignado`: Decimal128  
* `presupuesto_consumido_real`: Decimal128  
* `estado`: String (Enum: ABIERTO, CERRADO)

### **7\. Recepciones\_Logistica (Cálculo de Riesgo Dinámico)**

* `_id`: ObjectID  
* `orden_compra_id`: ObjectID (Ref: Ordenes\_Compra)  
* `sku_id`: ObjectID (Ref: Productos)  
* `cantidad_prometida`: Integer  
* `cantidad_recibida_real`: Integer  
* `fecha_entrega_prometida`: Date (ISO)  
* `fecha_recepcion_real`: Date (ISO)  
* `estado_calidad`: String

### **8\. Almacenes (Restricción Multidimensional)**

* `_id`: ObjectID  
* `nombre_almacen`: String  
* `capacidad_total_volumen_cm3`: Double  
* `capacidad_ocupada_actual_cm3`: Double  
* `costo_mantenimiento_inventario_porcentaje`: Double

### **9\. Ordenes\_Compra (Salida del Optimizador)**

* `_id`: ObjectID  
* `codigo_orden`: String  
* `fecha_generacion`: Date (ISO)  
* `presupuesto_utilizado`: Decimal128  
* `estado`: String  
* `nivel_confianza_ml`: Double  
* `items`: Array de Objetos (sku\_id, cantidad\_sugerida\_ml, cantidad\_final\_aprobada, costo\_unitario, subtotal)  
* `audit`: Objeto { generado\_por: ObjectID, aprobado\_por: ObjectID }

---

## **Fase 2: Arquitectura para Futura Escalabilidad**

### **10\. Escalas\_Precios (Costos No Lineales)**

* `_id`: ObjectID  
* `proveedor_id`: ObjectID  
* `sku_id`: ObjectID  
* `rango_minimo`: Integer  
* `rango_maximo`: Integer  
* `precio_unitario_descuento`: Decimal128

### **11\. Auditoria\_Modelos\_ML (Trazabilidad MLOps)**

* `_id`: ObjectID  
* `version_modelo`: String  
* `fecha_entrenamiento`: Date (ISO)  
* `dataset_referencia`: String  
* `metricas_error`: Objeto { mape: Double, rmse: Double, mae: Double }  
* `estado_despliegue`: String

### **12\. Productos\_Sustitutos (Resiliencia)**

* `_id`: ObjectID  
* `sku_principal_id`: ObjectID  
* `sku_sustituto_id`: ObjectID  
* `ratio_equivalencia`: Double  
* `prioridad_reemplazo`: Integer

### **13\. Costos\_Landed (Costos en Destino)**

* `_id`: ObjectID  
* `sku_id`: ObjectID  
* `proveedor_id`: ObjectID  
* `costo_flete_estimado`: Decimal128  
* `arancel_importacion_porcentaje`: Double  
* `seguro_logistico`: Decimal128  
* `costo_total_puesto_en_almacen`: Decimal128

### **14\. Variables\_Macroeconomicas (Riesgo Cambiario)**

* `_id`: ObjectID  
* `fecha`: Date (ISO)  
* `paridad_moneda`: String  
* `tipo_cambio_cierre`: Double  
* `tasa_inflacion_mensual`: Double

### **15\. Feedback\_Humano\_IA (RLHF)**

* `_id`: ObjectID  
* `orden_compra_id`: ObjectID  
* `sku_id`: ObjectID  
* `usuario_id`: ObjectID  
* `cantidad_sugerida_ml`: Integer  
* `cantidad_modificada`: Integer  
* `motivo_correccion`: String

### **16\. Consolidacion\_Carga (Optimización de Fletes)**

* `_id`: ObjectID  
* `orden_compra_id`: ObjectID  
* `tipo_contenedor`: String  
* `capacidad_maxima_volumen_cm3`: Double  
* `capacidad_maxima_peso_kg`: Double  
* `porcentaje_llenado_proyectado`: Double  
* `costo_fijo_transporte`: Decimal128

### **17\. Mermas\_y\_Devoluciones (Fugas de Inventario)**

* `_id`: ObjectID  
* `sku_id`: ObjectID  
* `fecha_registro`: Date (ISO)  
* `cantidad_afectada`: Integer  
* `tipo_movimiento`: String  
* `costo_perdido`: Decimal128