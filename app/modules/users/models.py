from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, utcnow

if TYPE_CHECKING:
    from app.modules.notifications.models import Notification
    from app.modules.projects.models import Project
    from app.modules.tasks.models import Task


class Role(str, enum.Enum):
    user = "user"
    admin = "admin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[Role] = mapped_column(Enum(Role, name="user_role"), default=Role.user, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    # один-ко-многим: пользователь владеет проектами
    projects: Mapped[list[Project]] = relationship(back_populates="owner", passive_deletes=True)
    # один-ко-многим: задачи, где пользователь — исполнитель
    assigned_tasks: Mapped[list[Task]] = relationship(back_populates="assignee", passive_deletes=True)
    # один-ко-многим: уведомления пользователя
    notifications: Mapped[list[Notification]] = relationship(back_populates="user", passive_deletes=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User id={self.id} email={self.email!r} role={self.role.value}>"
