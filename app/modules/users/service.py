from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestError, NotFoundError
from app.modules.notifications.models import Notification
from app.modules.projects.models import Project
from app.modules.tasks.models import Task, TaskStatus
from app.modules.users.models import Role, User
from app.modules.users.schemas import AdminStats


def get_user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError("Пользователь не найден")
    return user


def get_by_email(db: Session, email: str) -> User | None:
    return db.execute(select(User).where(User.email == email.lower())).scalar_one_or_none()


def list_users(db: Session, *, role: Role | None, limit: int, offset: int) -> list[User]:
    stmt = select(User).order_by(User.id).limit(limit).offset(offset)
    if role is not None:
        stmt = stmt.where(User.role == role)
    return list(db.execute(stmt).scalars())


def change_role(db: Session, *, acting_admin: User, user_id: int, role: Role) -> User:
    if acting_admin.id == user_id:
        # иначе последний админ может случайно лишить себя доступа
        raise BadRequestError("Нельзя изменить собственную роль")
    user = get_user(db, user_id)
    user.role = role
    db.commit()
    db.refresh(user)
    return user


def get_stats(db: Session) -> AdminStats:
    roles = dict(db.execute(select(User.role, func.count()).group_by(User.role)).all())
    statuses = dict(db.execute(select(Task.status, func.count()).group_by(Task.status)).all())
    return AdminStats(
        users=sum(roles.values()),
        admins=roles.get(Role.admin, 0),
        projects=db.scalar(select(func.count()).select_from(Project)) or 0,
        tasks_by_status={s.value: statuses.get(s, 0) for s in TaskStatus},
        notifications_unread=db.scalar(
            select(func.count()).select_from(Notification).where(Notification.is_read.is_(False))
        )
        or 0,
    )
