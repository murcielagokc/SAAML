from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from app.core.database import get_database
from app.core.security import create_access_token, decode_access_token, get_password_hash, verify_password
from app.models.schemas import RolUsuario, UsuarioModel

router = APIRouter(prefix="/auth", tags=["Autenticación"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str
    nombre_completo: str
    rol: RolUsuario = RolUsuario.OPERADOR


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    email: str
    rol: str


async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    email: str = payload.get("sub")
    db = get_database()
    user = await db["usuarios"].find_one({"email": email})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado"
        )
    if user.get("estado") != "ACTIVO":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario suspendido o bloqueado"
        )
    return user


@router.post("/register", response_model=dict, status_code=status.HTTP_201_CREATED)
async def register_user(user_in: UserRegisterRequest):
    """Registra un nuevo usuario con hashing seguro de contraseña."""
    db = get_database()
    existing = await db["usuarios"].find_one({"email": user_in.email.lower()})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe un usuario con este correo electrónico"
        )

    user_doc = {
        "email": user_in.email.lower(),
        "password_hash": get_password_hash(user_in.password),
        "nombre_completo": user_in.nombre_completo,
        "rol": user_in.rol.value,
        "estado": "ACTIVO",
        "intentos_fallidos": 0,
        "bloqueado_hasta": None,
        "token_version": 1,
        "ultimo_acceso": None,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    result = await db["usuarios"].insert_one(user_doc)
    return {
        "message": "Usuario creado exitosamente",
        "id": str(result.inserted_id),
        "email": user_doc["email"]
    }


@router.post("/login", response_model=TokenResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Autentica a un usuario y genera un JWT con expiración."""
    db = get_database()
    user = await db["usuarios"].find_one({"email": form_data.username.lower()})
    if not user or not verify_password(form_data.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas"
        )

    if user.get("estado") != "ACTIVO":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La cuenta se encuentra inactiva o bloqueada"
        )

    # Actualizar último acceso
    await db["usuarios"].update_one(
        {"_id": user["_id"]},
        {"$set": {"ultimo_acceso": datetime.utcnow(), "intentos_fallidos": 0}}
    )

    token = create_access_token(data={"sub": user["email"], "rol": user["rol"]})
    return TokenResponse(
        access_token=token,
        email=user["email"],
        rol=user["rol"]
    )


@router.get("/me")
async def read_current_user(current_user: dict = Depends(get_current_user)):
    """Retorna los datos del usuario autenticado actual."""
    return {
        "id": str(current_user["_id"]),
        "email": current_user["email"],
        "nombre_completo": current_user.get("nombre_completo"),
        "rol": current_user["rol"],
        "estado": current_user["estado"]
    }
