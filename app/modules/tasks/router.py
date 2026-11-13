from fastapi import APIRouter, Query, Response, status

from app.core.dependencies import CurrentUser, DbSession
from app.modules.notifications import service as notifications_service
from app.modules.tasks import service
from app.modules.tasks.models import Task, TaskStatus
from app.modules.tasks.schemas import TaskCreate, TaskOut, TaskUpdate

router = APIRouter(
    tags=["tasks"],
    responses={401: {"description": "Нет токена"}, 403: {"description": "Нет доступа"}, 404: {"description": "Не найдено"}},
)


def _out(task: Task, job_id: str | None = None) -> TaskOut:
    return TaskOut.model_validate(task).model_copy(update={"notification_job_id": job_id})


@router.post("/projects/{project_id}/tasks", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
def create_task(project_id: int, data: TaskCreate, db: DbSession, user: CurrentUser) -> TaskOut:
    """Создать задачу в своём проекте.

    Если указан исполнитель, через Celery `.delay()` ставится фоновая задача: она «отправляет письмо»
    и создаёт исполнителю уведомление. Ответ приходит сразу, id фоновой задачи — в `notification_job_id`.
    """
    task = service.create(db, user, project_id, data)
    job_id = notifications_service.queue_task_assigned(task.id) if task.assignee_id else None
    return _out(task, job_id)


@router.get("/projects/{project_id}/tasks", response_model=list[TaskOut])
def list_project_tasks(
    project_id: int,
    db: DbSession,
    user: CurrentUser,
    status_filter: TaskStatus | None = Query(None, alias="status"),
    tag: str | None = None,
    assignee_id: int | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[TaskOut]:
    """Задачи проекта с фильтрами по статусу, тегу и исполнителю."""
    tasks = service.list_project_tasks(
        db, user, project_id, status=status_filter, tag=tag, assignee_id=assignee_id, limit=limit, offset=offset
    )
    return [_out(t) for t in tasks]


@router.get("/tasks/assigned", response_model=list[TaskOut])
def list_assigned(
    db: DbSession, user: CurrentUser, status_filter: TaskStatus | None = Query(None, alias="status")
) -> list[TaskOut]:
    """Задачи, где я исполнитель: сначала высокий приоритет, затем ближайший срок."""
    return [_out(t) for t in service.list_assigned(db, user, status=status_filter)]


@router.get("/tasks/{task_id}", response_model=TaskOut)
def get_task(task_id: int, db: DbSession, user: CurrentUser) -> TaskOut:
    return _out(service.get_visible(db, user, task_id))


@router.patch("/tasks/{task_id}", response_model=TaskOut)
def update_task(task_id: int, data: TaskUpdate, db: DbSession, user: CurrentUser) -> TaskOut:
    """Изменить задачу. Владелец проекта меняет всё, исполнитель — только `status`.

    Смена исполнителя → уведомление новому исполнителю; перевод в `done` → уведомление владельцу проекта.
    """
    change = service.update(db, user, task_id, data)
    job_id = None
    if change.assignee_changed:
        job_id = notifications_service.queue_task_assigned(change.task.id)
    if change.completed and change.task.project.owner_id != user.id:
        job_id = notifications_service.queue_task_completed(change.task.id) or job_id
    return _out(change.task, job_id)


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int, db: DbSession, user: CurrentUser) -> Response:
    service.delete(db, user, task_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
