"""Инфраструктура: health-check, CORS, настройки, миграции Alembic."""

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from tests.helpers import auth


def test_health(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"


def test_cors_allowed_origin(client):
    r = client.options(
        "/auth/login", headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"}
    )
    assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_cors_foreign_origin_rejected(client):
    r = client.options("/auth/login", headers={"Origin": "http://evil.com", "Access-Control-Request-Method": "POST"})
    assert r.headers.get("access-control-allow-origin") is None


def test_cors_wildcard_forbidden():
    from pydantic import ValidationError

    from app.core.config import Settings

    with pytest.raises(ValidationError):
        Settings(CORS_ORIGINS="*")


def test_database_url_normalized():
    from app.core.config import Settings

    assert Settings(DATABASE_URL="postgresql://u:p@db/app").DATABASE_URL == "postgresql+psycopg://u:p@db/app"


def test_celery_urls_from_redis_url(monkeypatch):
    from app.core.config import Settings

    monkeypatch.delenv("CELERY_BROKER_URL", raising=False)
    monkeypatch.delenv("CELERY_RESULT_BACKEND", raising=False)
    s = Settings(REDIS_URL="redis://default:secret@redis.railway.internal:6379")
    assert s.CELERY_BROKER_URL == "redis://default:secret@redis.railway.internal:6379/0"
    assert s.CELERY_RESULT_BACKEND == "redis://default:secret@redis.railway.internal:6379/1"


def test_unknown_route_404(client, alice):
    assert client.get("/nope", headers=auth(alice)).status_code == 404


# ---------- Alembic ----------

EXPECTED_TABLES = {"users", "projects", "tasks", "tags", "task_tags", "notifications", "alembic_version"}


def _alembic(url: str) -> Config:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def test_migrations_upgrade_and_downgrade(tmp_path):
    """Схема создаётся миграциями, совпадает с моделями и полностью откатывается."""
    url = f"sqlite:///{tmp_path / 'migrations.db'}"
    cfg = _alembic(url)
    engine = create_engine(url)

    command.upgrade(cfg, "head")
    insp = inspect(engine)
    assert set(insp.get_table_names()) == EXPECTED_TABLES
    assert "priority" in {c["name"] for c in insp.get_columns("tasks")}  # миграция 0002

    fks = {(fk["constrained_columns"][0], fk["referred_table"]) for fk in insp.get_foreign_keys("tasks")}
    assert fks == {("project_id", "projects"), ("assignee_id", "users")}

    command.check(cfg)  # бросит исключение, если модели разошлись с миграциями

    command.downgrade(cfg, "0001")
    assert "priority" not in {c["name"] for c in inspect(engine).get_columns("tasks")}

    command.downgrade(cfg, "base")
    assert set(inspect(engine).get_table_names()) == {"alembic_version"}
    engine.dispose()
