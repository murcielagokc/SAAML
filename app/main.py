import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import httpx
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import close_mongo_connection, connect_to_mongo
from app.core.init_db import create_indexes

# Configuración de logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("saaml.main")


async def ping_keep_alive():
    """
    Tarea en segundo plano que realiza un ping HTTP cada N minutos
    para evitar que Render duerma el servidor en el tier gratuito.
    """
    interval_seconds = max(60, settings.KEEP_ALIVE_INTERVAL_MINUTES * 60)
    logger.info(f"Keep-Alive activado (frecuencia: cada {settings.KEEP_ALIVE_INTERVAL_MINUTES} min).")

    # Esperar 15 segundos iniciales para permitir que el servidor termine de arrancar
    await asyncio.sleep(15)

    while True:
        target_base = settings.RENDER_EXTERNAL_URL
        if not target_base:
            target_base = f"http://127.0.0.1:{settings.PORT}"

        health_url = f"{target_base.rstrip('/')}{settings.API_V1_STR}/health"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(health_url)
                if res.status_code == 200:
                    logger.info(f"[Keep-Alive] Ping exitoso a {health_url} (HTTP {res.status_code})")
                else:
                    logger.warning(f"[Keep-Alive] Ping a {health_url} respondió con status {res.status_code}")
        except Exception as e:
            logger.debug(f"[Keep-Alive] Ping no completado: {e}")

        await asyncio.sleep(interval_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gestión del ciclo de vida de la aplicación:
    - Conectar a MongoDB
    - Crear y verificar índices
    - Iniciar tarea Keep-Alive de auto-ping anti-inactividad
    - Liberar recursos al apagar
    """
    logger.info("Iniciando aplicación SAAML...")
    await connect_to_mongo()
    await create_indexes()

    keep_alive_task = None
    if settings.ENABLE_KEEP_ALIVE:
        keep_alive_task = asyncio.create_task(ping_keep_alive())

    yield

    logger.info("Apagando aplicación SAAML...")
    if keep_alive_task:
        keep_alive_task.cancel()
        try:
            await keep_alive_task
        except asyncio.CancelledError:
            pass
    await close_mongo_connection()



app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Sistema de Aprovisionamiento Autónomo basado en Machine Learning y Restricciones Presupuestales.",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registrar rutas con prefijo /api/v1
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/", tags=["Root"])
def root():
    return {
        "message": f"Bienvenido a la API de {settings.PROJECT_NAME}",
        "docs": "/docs",
        "version": settings.VERSION,
        "health": f"{settings.API_V1_STR}/health"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
