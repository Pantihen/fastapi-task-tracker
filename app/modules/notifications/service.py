import logging

from celery import Task as CeleryTask
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.celery_app import celery_app
from app.core.exceptions import NotFoundError
from app.modules.notifications import tasks
from app.modules.notifications.models import Notification
from app.modules.notifications.schemas import JobStatus
from app.modules.users.models import User

logger = logging.getLogger(__name__)


# ---------- Постановка фоновых задач ----------


def _queue(task: CeleryTask, *args: object) -> str | None:
    """task.delay(...) → id задачи. Если брокер недоступен, основное действие не ломается: вернётся None."""
    try:
        return task.delay(*args).id
    except Exception:
        logger.exception("Не удалось поставить задачу %s в очередь", task.name)
        return None


def queue_welcome(user_id: int) -> str | None:
    return _queue(tasks.send_welcome, user_id)


def queue_task_assigned(task_id: int) -> str | None:
    return _queue(tasks.task_assigned, task_id)


def queue_task_completed(task_id: int) -> str | None:
    return _queue(tasks.task_completed, task_id)


def job_status(job_id: str) -> JobStatus:
    result = celery_app.AsyncResult(job_id)
    status = JobStatus(job_id=job_id, status=result.status, ready=result.ready())
    if result.successful():
        status.result = result.result
    elif result.failed():
        status.error = str(result.result)
    return status


# ---------- Уведомления пользователя ----------


def list_for_user(db: Session, user: User, *, unread_only: bool, limit: int, offset: int) -> list[Notification]:
    stmt = (
        select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(limit)
        .offset(offset)
    )
    if unread_only:
        stmt = stmt.where(Notification.is_read.is_(False))
    return list(db.execute(stmt).scalars())


def mark_read(db: Session, user: User, notification_id: int) -> Notification:
    notification = db.get(Notification, notification_id)
    # чужое уведомление — 404, чтобы не раскрывать, что оно существует
    if notification is None or notification.user_id != user.id:
        raise NotFoundError("Уведомление не найдено")
    notification.is_read = True
    db.commit()
    db.refresh(notification)
    return notification
