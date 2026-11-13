from fastapi import APIRouter, Query, Response, status

from app.core.dependencies import CurrentUser, DbSession
from app.modules.projects import service
from app.modules.projects.schemas import ProjectCreate, ProjectOut, ProjectUpdate

router = APIRouter(
    prefix="/projects",
    tags=["projects"],
    responses={401: {"description": "Нет токена"}, 403: {"description": "Не владелец"}, 404: {"description": "Не найдено"}},
)


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(data: ProjectCreate, db: DbSession, user: CurrentUser) -> ProjectOut:
    """Создать проект. Владелец — текущий пользователь."""
    return service.to_out(db, [service.create(db, user, data)])[0]


@router.get("", response_model=list[ProjectOut])
def list_projects(
    db: DbSession,
    user: CurrentUser,
    all_projects: bool = Query(False, alias="all", description="Только для admin: проекты всех пользователей"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[ProjectOut]:
    """Мои проекты (у администратора с `all=true` — все)."""
    return service.to_out(db, service.list_for(db, user, limit=limit, offset=offset, all_projects=all_projects))


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: int, db: DbSession, user: CurrentUser) -> ProjectOut:
    return service.to_out(db, [service.get_manageable(db, user, project_id)])[0]


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(project_id: int, data: ProjectUpdate, db: DbSession, user: CurrentUser) -> ProjectOut:
    return service.to_out(db, [service.update(db, user, project_id, data)])[0]


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: int, db: DbSession, user: CurrentUser) -> Response:
    """Удалить проект вместе со всеми задачами."""
    service.delete(db, user, project_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
