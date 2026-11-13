from __future__ import annotations

import enum
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Column, Date, Enum, ForeignKey, Integer, SmallInteger, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.modules.projects.models import Project
    from app.modules.users.models import User


class TaskStatus(str, enum.Enum):
    todo = "todo"
    in_progress = "in_progress"
    done = "done"


# Таблица связи многие-ко-многим: задача ↔ тег
task_tags = Table(
    "task_tags",
    Base.metadata,
    Column("task_id", ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)

    tasks: Mapped[list[Task]] = relationship(secondary=task_tags, back_populates="tags")


class Task(TimestampMixin, Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, name="task_status"), default=TaskStatus.todo, index=True, nullable=False
    )
    due_date: Mapped[date | None] = mapped_column(Date)
    # добавлено миграцией 0002: 1 — низкий, 2 — обычный, 3 — высокий
    priority: Mapped[int] = mapped_column(SmallInteger, default=2, server_default="2", index=True, nullable=False)

    # многие-к-одному: задача принадлежит проекту
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # многие-к-одному: исполнитель; при удалении пользователя задача остаётся без исполнителя
    assignee_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )

    project: Mapped[Project] = relationship(back_populates="tasks")
    assignee: Mapped[User | None] = relationship(back_populates="assigned_tasks", lazy="selectin")
    # многие-ко-многим
    tags: Mapped[list[Tag]] = relationship(
        secondary=task_tags, back_populates="tasks", lazy="selectin", order_by="Tag.name"
    )
