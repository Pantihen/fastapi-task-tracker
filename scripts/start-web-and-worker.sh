#!/bin/sh
# Миграции + API + Celery-воркер в одном контейнере.
# Для хостинга, где отдельный сервис под воркер платный (Railway, Render free).
# В docker compose воркер — отдельный сервис, этот скрипт там не используется.
set -e

# отдельная база на общем сервере PostgreSQL создаётся при первом запуске
python -m scripts.ensure_database
alembic upgrade head

# --pool=solo — один процесс, минимум памяти.
# --without-gossip/mingle/heartbeat — воркер не обменивается служебными сообщениями с другими воркерами:
# pub/sub в Redis общий для всех баз, а на сервере Redis делят два проекта.
celery -A app.core.celery_app worker --loglevel=info --pool=solo --without-gossip --without-mingle --without-heartbeat &

# exec — uvicorn становится главным процессом и получает сигналы остановки от платформы
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips='*'
