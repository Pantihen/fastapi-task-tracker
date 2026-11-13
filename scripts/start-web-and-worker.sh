#!/bin/sh
# Миграции + API + Celery-воркер в одном контейнере.
# Для хостинга, где отдельный сервис под воркер платный (Railway, Render free).
# В docker compose воркер — отдельный сервис, этот скрипт там не используется.
set -e

alembic upgrade head

# --pool=solo — один процесс, минимум памяти
celery -A app.core.celery_app worker --loglevel=info --pool=solo &

# exec — uvicorn становится главным процессом и получает сигналы остановки от платформы
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips='*'
