import logging
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.core.config import settings

logger = logging.getLogger("saaml.database")


class DatabaseManager:
    client: Optional[AsyncIOMotorClient] = None
    db: Optional[AsyncIOMotorDatabase] = None
    is_connected: bool = False


db_manager = DatabaseManager()


async def connect_to_mongo():
    logger.info(f"Intentando conectar a MongoDB en: {settings.MONGODB_URI}")
    try:
        db_manager.client = AsyncIOMotorClient(
            settings.MONGODB_URI,
            serverSelectionTimeoutMS=5000
        )
        db_manager.db = db_manager.client[settings.MONGODB_DB_NAME]
        # Ping a la base de datos para verificar conexión real
        await db_manager.client.admin.command('ping')
        db_manager.is_connected = True
        logger.info(f"Conexión exitosa a la base de datos: {settings.MONGODB_DB_NAME}")
    except Exception as e:
        db_manager.is_connected = False
        logger.warning(
            f"No se pudo conectar a MongoDB ({e}). "
            f"El backend iniciará en modo desconectado. Configura MONGODB_URI en .env cuando esté lista."
        )


async def close_mongo_connection():
    if db_manager.client:
        logger.info("Cerrando conexión con MongoDB...")
        db_manager.client.close()
        db_manager.is_connected = False
        logger.info("Conexión con MongoDB cerrada.")


def get_database() -> AsyncIOMotorDatabase:
    if db_manager.db is None:
        raise RuntimeError(
            "La base de datos MongoDB no está disponible. "
            "Verifica la variable MONGODB_URI en tu archivo .env."
        )
    return db_manager.db
