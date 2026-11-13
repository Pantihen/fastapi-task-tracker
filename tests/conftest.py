import os
import tempfile

# Настройки для тестов задаются до импорта приложения.
# В CI передаётся TEST_DATABASE_URL с PostgreSQL, локально по умолчанию — временный SQLite.
_tmp_dir = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", f"sqlite:///{os.path.join(_tmp_dir, 'test.db')}")
os.environ["ADMIN_EMAIL"] = "admin@example.com"
os.environ["ADMIN_PASSWORD"] = "Admin12345"
os.environ["CORS_ORIGINS"] = "http://localhost:3000"
# Celery без Redis и воркера: задачи выполняются сразу, результаты — в памяти
os.environ["CELERY_BROKER_URL"] = "memory://"
os.environ["CELERY_RESULT_BACKEND"] = "cache+memory://"
os.environ["CELERY_TASK_ALWAYS_EAGER"] = "true"
os.environ["EMAIL_SEND_DELAY_SECONDS"] = "0"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import Base, engine  # noqa: E402
from app.core.rate_limit import limiter  # noqa: E402
from app.main import app  # noqa: E402
from tests.helpers import ADMIN, register, token_for  # noqa: E402


@pytest.fixture()
def client():
    # Чистая схема на каждый тест. Сами миграции проверяются отдельно в test_migrations.py
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    limiter.reset()
    with TestClient(app) as c:  # lifespan создаёт администратора
        yield c


@pytest.fixture()
def alice(client) -> dict:
    """Обычный пользователь — владелец проектов."""
    return register(client, "alice@example.com")


@pytest.fixture()
def bob(client) -> dict:
    """Второй обычный пользователь — исполнитель задач."""
    return register(client, "bob@example.com")


@pytest.fixture()
def admin(client) -> dict:
    return {"email": ADMIN["email"], "token": token_for(ADMIN["email"])}
