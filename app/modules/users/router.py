from fastapi import APIRouter, Depends, Query

from app.core.dependencies import AdminUser, CurrentUser, DbSession, require_role
from app.modules.users import service
from app.modules.users.models import Role, User
from app.modules.users.schemas import AdminStats, RoleUpdate, UserOut

ERRORS_401 = {401: {"description": "Нет токена или токен недействителен"}}

router = APIRouter(prefix="/users", tags=["users"], responses=ERRORS_401)


@router.get("/me", response_model=UserOut)
def read_me(current_user: CurrentUser) -> User:
    """Профиль текущего пользователя."""
    return current_user


# ---------- Администрирование: весь роутер только для роли admin (RBAC) ----------

admin_router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_role(Role.admin))],
    responses={**ERRORS_401, 403: {"description": "Нужна роль admin"}},
)


@admin_router.get("/users", response_model=list[UserOut])
def list_users(
    db: DbSession,
    role: Role | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[User]:
    """Все пользователи (фильтр по роли, пагинация)."""
    return service.list_users(db, role=role, limit=limit, offset=offset)


@admin_router.patch("/users/{user_id}/role", response_model=UserOut, responses={404: {}, 400: {}})
def change_role(user_id: int, data: RoleUpdate, db: DbSession, admin: AdminUser) -> User:
    """Назначить пользователю роль. Свою роль менять нельзя."""
    return service.change_role(db, acting_admin=admin, user_id=user_id, role=data.role)


@admin_router.get("/stats", response_model=AdminStats)
def stats(db: DbSession) -> AdminStats:
    """Сводка по системе: пользователи, проекты, задачи по статусам."""
    return service.get_stats(db)
