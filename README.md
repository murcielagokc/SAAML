# SAAML - Sistema de Aprovisionamiento Autónomo basado en Machine Learning y Restricciones Presupuestales

API RESTful desarrollada en **FastAPI** con persistencia NoSQL en **MongoDB** y motor de investigación de operaciones (optimización tipo *Knapsack*).

---

## 🚀 Arquitectura del Proyecto

```text
SAAML/
│
├── .venv/                         # Entorno virtual de Python 3.11
├── .env                           # Variables de entorno activas
├── .env.example                   # Plantilla de variables de entorno
├── requirements.txt               # Dependencias del proyecto
├── models.py                      # Modelos base Pydantic v2
├── pytest.ini                     # Configuración de pruebas unitarias
│
├── app/
│   ├── main.py                    # Punto de entrada FastAPI (lifespan, CORS, docs)
│   ├── core/
│   │   ├── config.py              # Pydantic Settings (.env)
│   │   ├── database.py            # Motor MongoDB Async Client (Motor)
│   │   ├── security.py            # Hashing Bcrypt y JWT (RNF-SEG)
│   │   └── init_db.py             # Creación de índices estratégicos de BD
│   ├── services/
│   │   ├── ml_engine.py           # Inferencia autoregresiva y reentrenamiento (RF02, RF06)
│   │   └── optimizer.py           # Motor Knapsack MILP con PuLP (RF04, RNF01)
│   └── api/
│       └── v1/
│           ├── router.py          # Enrutador central v1
│           └── endpoints/
│               ├── health.py      # Diagnóstico y estado de base de datos
│               ├── auth.py        # Registro, login JWT y control de roles
│               ├── products.py    # Catálogo de productos y carga batch (RF01)
│               ├── suppliers.py   # Gestión de proveedores y lead times
│               ├── sales.py       # Ingesta de ventas históricas por SKU (RF01)
│               ├── budget.py      # Ciclos de restricción presupuestal (RF03)
│               ├── ml.py          # Pronósticos de demanda y re-entrenamiento (RF02, RF06)
│               ├── optimization.py # Sesiones de optimización Knapsack (RF04)
│               └── orders.py      # Generación y aprobación de órdenes de compra (RF05)
│
├── scripts/
│   ├── seed_data.py               # Generador de datos semilla y ventas simuladas
│   └── test_db_connection.py     # Verificación de conexión a MongoDB
│
└── tests/
    └── test_api.py                # Tests unitarios e integración punta a punta

```

---

## 🛠️ Instalación y Puesta en Marcha

### 1. Activar Entorno Virtual
```powershell
.\.venv\Scripts\Activate.ps1
```

### 2. Configurar Base de Datos
En `.env`, asegúrate de configurar tu cadena de conexión a MongoDB (Local o MongoDB Atlas):
```env
MONGODB_URI="mongodb://localhost:27017" # o mongodb+srv://...
MONGODB_DB_NAME="saaml_db"
```

### 3. Sembrar Datos de Prueba (Opcional)
Genera proveedores, productos y 180 días de series temporales de ventas para entrenar ML:
```powershell
python scripts/seed_data.py
```

### 4. Iniciar el Servidor de Desarrollo
```powershell
uvicorn app.main:app --reload --port 8000
```

### 5. Documentación Interactiva (Swagger / OpenAPI)
Una vez iniciado el servidor, accede desde el navegador a:
* **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
* **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)
* **Health Check:** [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)

---

## 🧪 Ejecución de Pruebas
```powershell
pytest -v
```
