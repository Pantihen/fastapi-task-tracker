from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.modules.projects import service as projects_service
from app.modules.tasks.models import Tag, Task, TaskStatus
from app.modules.tasks.schemas import TaskCreate, TaskUpdate
from app.modules.users.models import User


@dataclass
class TaskChange:
    """Результат изменения задачи: что произошло — нужно роутеру, чтобы поставить уведомления."""

    task: Task
    assignee_changed: bool = False
    completed: bool = False


def _get_or_create_tags(db: Session, names: list[str]) -> list[Tag]:
    if not names:
        return []
    existing = {t.name: t for t in db.execute(select(Tag).where(Tag.name.in_(names))).scalars()}
    tags = []
    for name in names:
        tag = existing.get(name)
        if tag is None:
            tag = Tag(name=name)
            db.add(tag)
        tags.append(tag)
    return tags


def _check_assignee(db: Session, assignee_id: int | None) -> None:
    if assignee_id is not None and db.get(User, assignee_id) is None:
        raise BadRequestError("Исполнитель с таким id не найден")


def get_task(db: Session, task_id: int) -> Task:
    task = db.get(Task, task_id)
    if task is None:
        raise NotFoundError("Задача не найдена")
    return task


def get_visible(db: Session, user: User, task_id: int) -> Task:
    """Задачу видят владелец проекта, администратор и исполнитель."""
    task = get_task(db, task_id)
    if not (projects_service.can_manage(user, task.project) or task.assignee_id == user.id):
        raise ForbiddenError("Нет доступа к задаче")
    return task


def create(db: Session, user: User, project_id: int, data: TaskCreate) -> Task:
    project = projects_service.get_manageable(db, user, project_id)
    _check_assignee(db, data.assignee_id)
    task = Task(
        title=data.title,
        description=data.description,
        status=data.status,
        due_date=data.due_date,
        priority=data.priority,
        assignee_id=data.assignee_id,
        project_id=project.id,
        tags=_get_or_create_tags(db, data.tags),
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def list_project_tasks(
    db: Session,
    user: User,
    project_id: int,
    *,
    status: TaskStatus | None,
    tag: str | None,
    assignee_id: int | None,
    limit: int,
    offset: int,
) -> list[Task]:
    projects_service.get_manageable(db, user, project_id)
    stmt = select(Task).where(Task.project_id == project_id).order_by(Task.id).limit(limit).offset(offset)
    if status is not None:
        stmt = stmt.where(Task.status == status)
    if assignee_id is not None:
        stmt = stmt.where(Task.assignee_id == assignee_id)
    if tag:
        stmt = stmt.where(Task.tags.any(Tag.name == tag.strip().lower()))
    return list(db.execute(stmt).scalars())


def list_assigned(db: Session, user: User, *, status: TaskStatus | None) -> list[Task]:
    """Мои задачи: сначала с высоким приоритетом, затем по ближайшему сроку."""
    stmt = (
        select(Task)
        .where(Task.assignee_id == user.id)
        .order_by(Task.priority.desc(), Task.due_date.is_(None), Task.due_date, Task.id)
    )
    if status is not None:
        stmt = stmt.where(Task.status == status)
    return list(db.execute(stmt).scalars())


def update(db: Session, user: User, task_id: int, data: TaskUpdate) -> TaskChange:
    task = get_task(db, task_id)
    manager = projects_service.can_manage(user, task.project)
    assignee = task.assignee_id == user.id
    if not (manager or assignee):
        raise ForbiddenError("Нет доступа к задаче")

    changes = data.model_dump(exclude_unset=True)
    if not manager and set(changes) - {"status"}:
        raise ForbiddenError("Исполнитель может менять только статус задачи")
    for field in ("title", "status", "priority"):
        if field in changes and changes[field] is None:
            raise BadRequestError(f"Поле {field} не может быть пустым")
    if "assignee_id" in changes:
        _check_assignee(db, changes["assignee_id"])

    old_assignee, old_status = task.assignee_id, task.status
    tags = changes.pop("tags", None)
    for field, value in changes.items():
        setattr(task, field, value)
    if tags is not None:
        task.tags = _get_or_create_tags(db, tags)

    db.commit()
    db.refresh(task)
    return TaskChange(
        task=task,
        assignee_changed=task.assignee_id is not None and task.assignee_id != old_assignee,
        completed=old_status != TaskStatus.done and task.status == TaskStatus.done,
    )


def delete(db: Session, user: User, task_id: int) -> None:
    task = get_task(db, task_id)
    if not projects_service.can_manage(user, task.project):
        raise ForbiddenError("Удалять задачи может только владелец проекта")
    db.delete(task)
    db.commit()
