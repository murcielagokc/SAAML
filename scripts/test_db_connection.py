"""
Script de diagnóstico para probar la conexión con MongoDB (Atlas o Local).
Uso:
    python scripts/test_db_connection.py
"""

import asyncio
import sys
from pathlib import Path

# Asegurar que el directorio raíz del proyecto esté en el PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings


async def test_connection():
    print("=" * 60)
    print(" [DIAGNÓSTICO] Probando conexión a MongoDB...")
    print(f" -> MONGODB_URI:     {settings.MONGODB_URI}")
    print(f" -> MONGODB_DB_NAME: {settings.MONGODB_DB_NAME}")
    print("=" * 60)

    if "localhost" in settings.MONGODB_URI or "127.0.0.1" in settings.MONGODB_URI:
        print("[!] Aviso: Estás apuntando a localhost/127.0.0.1.")
        print("    Si vas a usar MongoDB Atlas en la nube, debes cambiar MONGODB_URI en tu archivo .env\n")

    client = AsyncIOMotorClient(settings.MONGODB_URI, serverSelectionTimeoutMS=5000)
    try:
        print("[*] Enviando ping al servidor MongoDB...")
        await client.admin.command('ping')
        print("[OK] CONEXION EXITOSA CON MONGODB ATLAS!")
        
        db = client[settings.MONGODB_DB_NAME]
        collections = await db.list_collection_names()
        print(f"[*] Base de datos activa: '{settings.MONGODB_DB_NAME}'")
        print(f"[*] Colecciones existentes: {collections if collections else 'Ninguna todavia (base de datos limpia)'}")
        print("\nTodo esta listo para ejecutar la API o sembrar datos con 'python scripts/seed_data.py'.")
    except Exception as e:
        print("\n[ERROR] AL CONECTAR CON MONGODB:")
        print(f"    {e}\n")
        print("POSIBLES SOLUCIONES:")
        print("1. Si usas MongoDB Atlas:")
        print("   - Revisa que tu usuario y contraseña sean correctos en el archivo .env.")
        print("   - Asegúrate de habilitar el acceso por IP (0.0.0.0/0) en 'Network Access' dentro de Atlas.")
        print("2. Si usas MongoDB Local:")
        print("   - Inicia el servicio de MongoDB en tu máquina de Windows.")
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(test_connection())
