from functools import lru_cache
from urllib.parse import urlsplit, urlunsplit

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _redis_url_with_db(url: str, db: int) -> str:
    """redis://host:6379 или redis://host:6379/0 → redis://host:6379/<db> (логин, пароль и параметры сохраняются)."""
    parts = urlsplit(url.strip())
    return urlunsplit((parts.scheme, parts.netloc, f"/{db}", parts.query, parts.fragment))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    SECRET_KEY: str = "dev-secret-change-me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    DATABASE_URL: str = "sqlite:///./app.db"

    # Строка с origin через запятую, например "http://localhost:3000,http://localhost:5173"
    CORS_ORIGINS: str = "http://localhost:3000"

    LOGIN_RATE_LIMIT: str = "5/minute"

    ADMIN_EMAIL: str | None = None
    ADMIN_PASSWORD: str | None = None

    # Явные адреса брокера и хранилища результатов. Если не заданы, они строятся
    # из REDIS_URL: тот же Redis, но разные номера баз (CELERY_*_DB).
    CELERY_BROKER_URL: str | None = None
    CELERY_RESULT_BACKEND: str | None = None
    REDIS_URL: str = "redis://localhost:6379"
    CELERY_BROKER_DB: int = 0
    CELERY_RESULT_DB: int = 1
    # В тестах True: задача выполняется сразу в том же процессе, без воркера и Redis
    CELERY_TASK_ALWAYS_EAGER: bool = False
    EMAIL_SEND_DELAY_SECONDS: float = 10

    @field_validator("CORS_ORIGINS")
    @classmethod
    def forbid_wildcard(cls, value: str) -> str:
        origins = [o.strip() for o in value.split(",") if o.strip()]
        if not origins:
            raise ValueError("CORS_ORIGINS должен содержать хотя бы один origin")
        if "*" in origins:
            raise ValueError("Wildcard '*' в CORS_ORIGINS запрещён — укажите origin явно")
        return value

    @field_validator("DATABASE_URL")
    @classmethod
    def use_psycopg_driver(cls, value: str) -> str:
        # Railway/Heroku выдают postgres:// или postgresql:// — SQLAlchemy нужен явный драйвер psycopg 3
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value[len(prefix):]
        return value

    @model_validator(mode="after")
    def build_celery_urls(self) -> "Settings":
        if self.CELERY_BROKER_URL is None:
            self.CELERY_BROKER_URL = _redis_url_with_db(self.REDIS_URL, self.CELERY_BROKER_DB)
        if self.CELERY_RESULT_BACKEND is None:
            self.CELERY_RESULT_BACKEND = _redis_url_with_db(self.REDIS_URL, self.CELERY_RESULT_DB)
        return self

    # Render сам задаёт публичный адрес сервиса, например https://my-app.onrender.com
    RENDER_EXTERNAL_URL: str | None = None

    @property
    def cors_origins_list(self) -> list[str]:
        origins = [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]
        if self.RENDER_EXTERNAL_URL and self.RENDER_EXTERNAL_URL not in origins:
            origins.append(self.RENDER_EXTERNAL_URL.rstrip("/"))
        return origins


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
