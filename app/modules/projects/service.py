from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenError, NotFoundError
from app.modules.projects.models import Project
from app.modules.projects.schemas import ProjectCreate, ProjectOut, ProjectUpdate
from app.modules.tasks.models import Task
from app.modules.users.models import Role, User


def can_manage(user: User, project: Project) -> bool:
    """Управлять проектом и его задачами может владелец или администратор."""
    return user.role == Role.admin or project.owner_id == user.id


def get_project(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise NotFoundError("Проект не найден")
    return project


def get_manageable(db: Session, user: User, project_id: int) -> Project:
    project = get_project(db, project_id)
    if not can_manage(user, project):
        raise ForbiddenError("Нет доступа к проекту: вы не владелец")
    return project


def _tasks_count(db: Session, project_ids: list[int]) -> dict[int, int]:
    if not project_ids:
        return {}
    rows = db.execute(
        select(Task.project_id, func.count(Task.id)).where(Task.project_id.in_(project_ids)).group_by(Task.project_id)
    ).all()
    return dict(rows)


def to_out(db: Session, projects: list[Project]) -> list[ProjectOut]:
    """Проекты + количество задач одним дополнительным запросом (без N+1)."""
    counts = _tasks_count(db, [p.id for p in projects])
    return [ProjectOut.model_validate(p).model_copy(update={"tasks_count": counts.get(p.id, 0)}) for p in projects]


def create(db: Session, owner: User, data: ProjectCreate) -> Project:
    project = Project(name=data.name, description=data.description, owner_id=owner.id)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def list_for(db: Session, user: User, *, limit: int, offset: int, all_projects: bool = False) -> list[Project]:
    """Свои проекты. Администратор с all_projects=True видит все."""
    stmt = select(Project).order_by(Project.id).limit(limit).offset(offset)
    if not (all_projects and user.role == Role.admin):
        stmt = stmt.where(Project.owner_id == user.id)
    return list(db.execute(stmt).scalars())


def update(db: Session, user: User, project_id: int, data: ProjectUpdate) -> Project:
    project = get_manageable(db, user, project_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    db.commit()
    db.refresh(project)
    return project


def delete(db: Session, user: User, project_id: int) -> None:
    project = get_manageable(db, user, project_id)
    db.delete(project)  # задачи удаляются каскадно
    db.commit()
