import json
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "QuanLyPhongTro"
    APP_ENV: str = "development"
    APP_DEBUG: bool = True

    DATABASE_URL: str
    DB_AUTO_CREATE_TABLES_ON_STARTUP: bool = False

    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    DEVELOPER_ACCESS_TOKEN_EXPIRE_MINUTES: int = 720
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"
    GOOGLE_CLIENT_ID: str = ""
    MINIO_ENDPOINT: str = "127.0.0.1:9000"
    MINIO_ACCESS_KEY: str = ""
    MINIO_SECRET_KEY: str = ""
    MINIO_ROOT_USER: str = "admin"
    MINIO_ROOT_PASSWORD: str = "password123"
    MINIO_SECURE: bool = False
    MINIO_CHAT_BUCKET: str = "qlpt-chat"

    REDIS_ENABLED: bool = True
    REDIS_HOST: str = "127.0.0.1"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str = ""
    PRESENCE_TTL_SECONDS: int = 45

    AGENT_DEFAULT_MODEL: str = "gpt-oss:120b-cloud"
    AGENT_CHEAP_MODEL: str = "kimi-k2.5:cloud"
    AGENT_MAX_TOOL_CALLS: int = 8
    AGENT_DEFAULT_TIMEOUT_SECONDS: int = 20
    AGENT_RETRY_LIMIT: int = 2
    AGENT_ENABLE_WRITE_ACTIONS: bool = False
    AGENT_REQUIRE_APPROVAL_FOR_WRITES: bool = True
    AGENT_DEFAULT_EXECUTION_MODE: str = "read_only"
    AGENT_CHECKPOINTER_BACKEND: str = "sqlite"  # db | sqlite
    AGENT_CHECKPOINTER_SQLITE_PATH: str = "./logs/agent_checkpoints.sqlite3"
    AGENT_TOKEN_BUDGET: int = 4000
    AGENT_COST_BUDGET_USD: float = 0.2
    OLLAMA_HOST: str = "http://127.0.0.1:11434"
    OLLAMA_API_KEY: str = ""
    OLLAMA_MODEL_FALLBACKS: str = ""

    CORS_ORIGINS: Annotated[list[str], NoDecode] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://nexus-pms-dashboard.vercel.app",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return []
            if text.startswith("["):
                try:
                    parsed = json.loads(text)
                except json.JSONDecodeError:
                    pass
                else:
                    if isinstance(parsed, list):
                        return [
                            str(origin).strip()
                            for origin in parsed
                            if str(origin).strip()
                        ]
            return [origin.strip() for origin in text.split(",") if origin.strip()]
        if isinstance(value, (tuple, set)):
            return [str(origin).strip() for origin in value if str(origin).strip()]
        return value

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
