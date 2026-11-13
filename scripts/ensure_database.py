"""Создаёт базу PostgreSQL из DATABASE_URL, если её ещё нет.

Нужно, когда приложение использует отдельную базу на общем сервере PostgreSQL
(например, на Railway рядом с другим проектом). Если база уже есть или это не PostgreSQL —
ничего не делает. Запускается перед `alembic upgrade head`.
"""

import re
import sys

import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url

from app.core.config import settings


def main() -> int:
    url = make_url(settings.DATABASE_URL)
    if not url.drivername.startswith("postgresql") or not url.database:
        return 0
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,62}", url.database):
        print(f"ensure_database: недопустимое имя базы {url.database!r}", file=sys.stderr)
        return 1

    conninfo = dict(host=url.host, port=url.port or 5432, user=url.username, password=url.password)
    try:
        with psycopg.connect(dbname=url.database, connect_timeout=10, **conninfo):
            return 0  # база уже есть
    except psycopg.OperationalError as exc:
        if "does not exist" not in str(exc):
            raise

    # CREATE DATABASE нельзя выполнить в транзакции — autocommit; имя экранируется как идентификатор
    with psycopg.connect(dbname="postgres", autocommit=True, connect_timeout=10, **conninfo) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(url.database)))
    print(f"ensure_database: создана база {url.database}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
