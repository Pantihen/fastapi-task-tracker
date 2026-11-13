"""Фоновые задачи Celery.

Выполняются в воркере, а не в процессе API: эндпоинт ставит задачу через .delay()
и сразу отвечает клиенту. Воркер «отправляет письмо» (долгая операция) и записывает
уведомление в PostgreSQL.
"""

import logging
import time

import app.models  # noqa: F401 — регистрирует все модели (воркер импортирует только этот модуль)
from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.database import SessionLocal
from app.modules.notifications.models import Notification
from app.modules.tasks.models import Task
from app.modules.users.models import User

logger = logging.getLogger(__name__)


def _deliver(user_id: int, message: str) -> dict:
    """Имитация отправки email + сохранение уведомления в БД."""
    with SessionLocal() as db:
        user = db.get(User, user_id)
        if user is None:
            return {"delivered": False, "reason": "user not found"}

        logger.info("Отправка письма на %s: %s", user.email, message)
        time.sleep(settings.EMAIL_SEND_DELAY_SECONDS)  # имитация SMTP

        notification = Notification(user_id=user.id, message=message)
        db.add(notification)
        db.commit()
        return {"delivered": True, "to": user.email, "notification_id": notification.id, "message": message}


@celery_app.task(name="notifications.send_welcome")
def send_welcome(user_id: int) -> dict:
    return _deliver(user_id, "Добро пожаловать в Task Tracker! Создайте первый проект.")


@celery_app.task(name="notifications.task_assigned")
def task_assigned(task_id: int) -> dict:
    with SessionLocal() as db:
        task = db.get(Task, task_id)
        if task is None or task.assignee_id is None:
            return {"delivered": False, "reason": "task not found or has no assignee"}
        assignee_id = task.assignee_id
        message = f"Вам назначена задача «{task.title}» в проекте «{task.project.name}»"
    return _deliver(assignee_id, message)


@celery_app.task(name="notifications.task_completed")
def task_completed(task_id: int) -> dict:
    with SessionLocal() as db:
        task = db.get(Task, task_id)
        if task is None:
            return {"delivered": False, "reason": "task not found"}
        owner_id = task.project.owner_id
        who = task.assignee.email if task.assignee else "исполнитель"
        message = f"{who} выполнил задачу «{task.title}» в проекте «{task.project.name}»"
    return _deliver(owner_id, message)
