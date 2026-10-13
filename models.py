"""
Modelos de Datos Pydantic v2 para FastAPI y MongoDB (SAAML)
Sistema de Aprovisionamiento Autónomo basado en ML y Restricciones Presupuestales
"""

from datetime import datetime
from enum import Enum
from typing import Annotated, Any, Dict, List, Optional
from pydantic import BaseModel, BeforeValidator, ConfigDict, EmailStr, Field


# Helper para manejar ObjectId de MongoDB en Pydantic v2
PyObjectId = Annotated[str, BeforeValidator(str)]


# --------------------------------------------------------------------------
# ENUMS DEL SISTEMA
# --------------------------------------------------------------------------
class RolUsuario(str, Enum):
    ADMIN = "ADMIN"
    GERENTE_COMPRAS = "GERENTE_COMPRAS"
    OPERADOR = "OPERADOR"
    SISTEMA_ML = "SISTEMA_ML"


class EstadoUsuario(str, Enum):
    ACTIVO = "ACTIVO"
    SUSPENDIDO = "SUSPENDIDO"
    BLOQUEADO = "BLOQUEADO"


class EstadoProveedor(str, Enum):
    ACTIVO = "ACTIVO"
    INACTIVO = "INACTIVO"


class EstadoProducto(str, Enum):
    ACTIVO = "ACTIVO"
    DISCONTINUADO = "DISCONTINUADO"


class CanalVenta(str, Enum):
    ONLINE = "ONLINE"
    RETAIL = "RETAIL"
    B2B = "B2B"


class TipoEvento(str, Enum):
    FERIADO = "FERIADO"
    CAMPANA = "CAMPAÑA"
    BLACK_FRIDAY = "BLACK_FRIDAY"
    CYBER_DAY = "CYBER_DAY"
    DESASTRE = "DESASTRE"


class EstadoCiclo(str, Enum):
    ABIERTO = "ABIERTO"
    CERRADO = "CERRADO"
    CONGELADO = "CONGELADO"


class EstadoDespliegueML(str, Enum):
    PRODUCCION = "PRODUCCION"
    STAGING = "STAGING"
    ARCHIVADO = "ARCHIVADO"


class SolverStatus(str, Enum):
    OPTIMAL = "OPTIMAL"
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    ERROR = "ERROR"


class EstadoOrdenCompra(str, Enum):
    BORRADOR_PROPUESTA = "BORRADOR_PROPUESTA"
    APROBADA = "APROBADA"
    ENVIADA_PROVEEDOR = "ENVIADA_PROVEEDOR"
    RECIBIDA_PARCIAL = "RECIBIDA_PARCIAL"
    RECIBIDA_TOTAL = "RECIBIDA_TOTAL"
    CANCELADA = "CANCELADA"


class EstadoCalidad(str, Enum):
    CONFORME = "CONFORME"
    RECHAZADO_PARCIAL = "RECHAZADO_PARCIAL"
    RECHAZADO_TOTAL = "RECHAZADO_TOTAL"


# --------------------------------------------------------------------------
# MODELOS DE BASE DE DATOS
# --------------------------------------------------------------------------

class MongoBaseModel(BaseModel):
    id: Optional[PyObjectId] = Field(default=None, alias="_id")

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True
    )


# 1. Usuarios (RNF-SEG)
class UsuarioModel(MongoBaseModel):
    email: EmailStr
    password_hash: str
    nombre_completo: str
    rol: RolUsuario = RolUsuario.OPERADOR
    estado: EstadoUsuario = EstadoUsuario.ACTIVO
    intentos_fallidos: int = 0
    bloqueado_hasta: Optional[datetime] = None
    token_version: int = 1
    ultimo_acceso: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# 2. Proveedores (RF01, RF04)
class ContactoProveedor(BaseModel):
    nombre: str
    email: EmailStr
    telefono: Optional[str] = None


class ProveedorModel(MongoBaseModel):
    codigo_proveedor: str
    nombre_empresa: str
    contacto: Optional[ContactoProveedor] = None
    moneda: str = "USD"
    condiciones_pago: str = "30_DIAS"
    calificacion_calidad: float = Field(ge=1.0, le=5.0, default=5.0)
    variabilidad_lead_time_dias: float = 0.0
    lead_time_promedio_dias: int = 7
    estado: EstadoProveedor = EstadoProveedor.ACTIVO
    created_at: datetime = Field(default_factory=datetime.utcnow)


# 3. Almacenes (RF04 - Restricción Volumétrica)
class AlmacenModel(MongoBaseModel):
    codigo_almacen: str
    nombre_almacen: str
    ubicacion: Optional[str] = None
    capacidad_total_volumen_cm3: float
    capacidad_ocupada_actual_cm3: float = 0.0
    costo_mantenimiento_inventario_porcentaje: float = 0.02
    estado: str = "ACTIVO"


# 4. Productos (RF01, RF04)
class AuditInfo(BaseModel):
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ProductoModel(MongoBaseModel):
    sku_code: str
    nombre: str
    categoria: str
    proveedor_id: PyObjectId
    almacen_id: PyObjectId
    costo_unitario: float
    precio_venta: float
    stock_actual: int
    stock_seguridad: int = 0
    moq: int = 1
    incremento_lote: int = 1
    volumen_cm3: float
    peso_kg: float = 0.0
    lead_time_promedio_dias: int = 7
    estado: EstadoProducto = EstadoProducto.ACTIVO
    audit: AuditInfo = Field(default_factory=AuditInfo)


# 5. Historial de Ventas (RF01, RF02 - ML Series de Tiempo)
class HistorialVentaModel(MongoBaseModel):
    sku_id: PyObjectId
    fecha: datetime
    cantidad_vendida: int
    precio_unitario_aplicado: float
    descuento_porcentaje: float = 0.0
    stockout_flag: bool = False
    canal_venta: CanalVenta = CanalVenta.RETAIL
    almacen_id: Optional[PyObjectId] = None


# 6. Eventos Calendario (RF02 - Variables Exógenas ML)
class EventoCalendarioModel(MongoBaseModel):
    nombre_evento: str
    tipo_evento: TipoEvento
    fecha_inicio: datetime
    fecha_fin: datetime
    multiplicador_esperado_demanda: float = 1.0
    categorias_afectadas: List[str] = Field(default_factory=list)


# 7. Ciclos Presupuestales (RF03)
class CicloPresupuestalModel(MongoBaseModel):
    codigo_ciclo: str
    periodo: str
    fecha_inicio: datetime
    fecha_fin: datetime
    presupuesto_total_asignado: float
    presupuesto_comprometido: float = 0.0
    presupuesto_consumido_real: float = 0.0
    estado: EstadoCiclo = EstadoCiclo.ABIERTO
    created_by: Optional[PyObjectId] = None


# 8. Modelos ML / MLOps (RF06)
class MetricasErrorML(BaseModel):
    mape: float
    rmse: float
    mae: float
    r2: Optional[float] = None


class ModeloMLModel(MongoBaseModel):
    version_modelo: str
    algoritmo: str
    fecha_entrenamiento: datetime = Field(default_factory=datetime.utcnow)
    dataset_referencia_hash: str
    hiperparametros: Dict[str, Any] = Field(default_factory=dict)
    metricas_error: MetricasErrorML
    artefacto_url: Optional[str] = None
    estado_despliegue: EstadoDespliegueML = EstadoDespliegueML.PRODUCCION


# 9. Predicciones Demanda (RF02, RF04)
class PrediccionDemandaModel(MongoBaseModel):
    modelo_version: str
    sku_id: PyObjectId
    fecha_generacion: datetime = Field(default_factory=datetime.utcnow)
    horizonte_dias: int
    fecha_inicio_proyeccion: datetime
    fecha_fin_proyeccion: datetime
    demanda_predicha: float
    intervalo_p10: Optional[float] = None
    intervalo_p90: Optional[float] = None
    stock_proyectado_agotamiento: Optional[datetime] = None


# 10. Sesiones de Optimización (RF04, RNF01)
class ParametrosOptimizacion(BaseModel):
    considerar_volumen_almacen: bool = True
    factor_seguridad: float = 1.0


class SesionOptimizacionModel(MongoBaseModel):
    ciclo_presupuestal_id: PyObjectId
    usuario_id: PyObjectId
    fecha_ejecucion: datetime = Field(default_factory=datetime.utcnow)
    presupuesto_disponible: float
    parametros_config: ParametrosOptimizacion = Field(default_factory=ParametrosOptimizacion)
    tiempo_ejecucion_ms: int
    solver_status: SolverStatus
    demanda_total_cubierta_porcentaje: float
    presupuesto_total_asignado: float
    skus_seleccionados_conteo: int


# 11. Ordenes de Compra (RF05)
class ItemOrdenCompra(BaseModel):
    sku_id: PyObjectId
    sku_code: str
    nombre_producto: str
    cantidad_sugerida_ml: int
    cantidad_final_aprobada: int
    costo_unitario: float
    subtotal: float
    volumen_total_cm3: float


class AuditOrdenCompra(BaseModel):
    generado_por: PyObjectId
    aprobado_por: Optional[PyObjectId] = None
    fecha_aprobacion: Optional[datetime] = None


class OrdenCompraModel(MongoBaseModel):
    codigo_orden: str
    sesion_optimizacion_id: Optional[PyObjectId] = None
    ciclo_presupuestal_id: PyObjectId
    proveedor_id: PyObjectId
    almacen_id: Optional[PyObjectId] = None
    fecha_generacion: datetime = Field(default_factory=datetime.utcnow)
    fecha_entrega_estimada: Optional[datetime] = None
    costo_total_orden: float
    estado: EstadoOrdenCompra = EstadoOrdenCompra.BORRADOR_PROPUESTA
    nivel_confianza_ml_promedio: float = 0.0
    items: List[ItemOrdenCompra]
    audit: AuditOrdenCompra


# 12. Recepciones Logísticas (Fase 1 / Desempeño)
class RecepcionLogisticaModel(MongoBaseModel):
    orden_compra_id: PyObjectId
    proveedor_id: PyObjectId
    sku_id: PyObjectId
    cantidad_prometida: int
    cantidad_recibida_real: int
    fecha_entrega_prometida: datetime
    fecha_recepcion_real: datetime
    dias_desviacion: int = 0
    estado_calidad: EstadoCalidad = EstadoCalidad.CONFORME
    created_at: datetime = Field(default_factory=datetime.utcnow)


# 13. Logs de Auditoría y Seguridad (RNF-SEG)
class LogSeguridadAuditoriaModel(MongoBaseModel):
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    usuario_id: Optional[PyObjectId] = None
    ip_origen: Optional[str] = None
    user_agent: Optional[str] = None
    accion: str
    recurso_afectado: str
    detalles: Dict[str, Any] = Field(default_factory=dict)
    nivel: str = "INFO"
