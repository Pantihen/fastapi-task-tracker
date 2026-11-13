from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr

from app.modules.users.models import Role


class UserBrief(BaseModel):
    """Короткое представление пользователя — для вложения в проекты и задачи."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr


class UserOut(UserBrief):
    role: Role
    created_at: datetime


class RoleUpdate(BaseModel):
    role: Role


class AdminStats(BaseModel):
    users: int
    admins: int
    projects: int
    tasks_by_status: dict[str, int]
    notifications_unread: int
