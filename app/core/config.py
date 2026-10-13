import json
from typing import List, Optional, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    PROJECT_NAME: str = "SAAML - Sistema de Aprovisionamiento Autónomo"
    VERSION: str = "1.0.0-beta"
    API_V1_STR: str = "/api/v1"
    PORT: int = 8000
    HOST: str = "0.0.0.0"

    # Base de Datos MongoDB
    MONGODB_URI: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "saaml_db"

    # Seguridad JWT (RNF-SEG)
    SECRET_KEY: str = "saaml_dev_secret_key_change_in_production_jwt_token_2026"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 horas

    # Restricciones y Rendimiento (RNF01)
    MAX_OPTIMIZATION_SECONDS: int = 30

    # Keep-Alive Anti-Sleep (Ping automático para evitar que Render se duerma)
    ENABLE_KEEP_ALIVE: bool = True
    KEEP_ALIVE_INTERVAL_MINUTES: int = 5
    RENDER_EXTERNAL_URL: Optional[str] = None

    # CORS
    CORS_ORIGINS: Union[List[str], str] = ["*"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            if v.strip().startswith("["):
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        return v

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
