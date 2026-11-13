from fastapi import APIRouter, Query

from app.core.dependencies import CurrentUser, DbSession
from app.modules.notifications import service
from app.modules.notifications.models import Notification
from app.modules.notifications.schemas import JobStatus, NotificationOut

router = APIRouter(prefix="/notifications", tags=["notifications"], responses={401: {"description": "Нет токена"}})


@router.get("", response_model=list[NotificationOut])
def list_notifications(
    db: DbSession,
    user: CurrentUser,
    unread: bool = Query(False, description="Только непрочитанные"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[Notification]:
    """Мои уведомления (их создают фоновые задачи Celery)."""
    return service.list_for_user(db, user, unread_only=unread, limit=limit, offset=offset)


@router.post("/{notification_id}/read", response_model=NotificationOut, responses={404: {}})
def mark_read(notification_id: int, db: DbSession, user: CurrentUser) -> Notification:
    return service.mark_read(db, user, notification_id)


@router.get("/jobs/{job_id}", response_model=JobStatus)
def job_status(job_id: str, _: CurrentUser) -> JobStatus:
    """Статус фоновой задачи Celery по id (из `welcome_job_id` или `notification_job_id`).

    PENDING — в очереди, STARTED — выполняется, SUCCESS — готово (в `result` итог).
    """
    return service.job_status(job_id)
