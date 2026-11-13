from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.tasks.models import TaskStatus
from app.modules.users.schemas import UserBrief


def _normalize_tags(tags: list[str] | None) -> list[str] | None:
    """Теги в нижнем регистре, без пробелов по краям и без повторов (порядок сохраняется)."""
    if tags is None:
        return None
    result: list[str] = []
    for raw in tags:
        tag = raw.strip().lower()
        if not tag:
            continue
        if len(tag) > 50:
            raise ValueError("Тег длиннее 50 символов")
        if tag not in result:
            result.append(tag)
    return result


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    status: TaskStatus = TaskStatus.todo
    due_date: date | None = None
    priority: int = Field(default=2, ge=1, le=3, description="1 — низкий, 2 — обычный, 3 — высокий")
    assignee_id: int | None = Field(default=None, description="Исполнитель — получит уведомление через Celery")
    tags: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str] | None) -> list[str] | None:
        return _normalize_tags(value)


class TaskUpdate(BaseModel):
    """Все поля необязательные. Исполнитель (не владелец проекта) может менять только status."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    status: TaskStatus | None = None
    due_date: date | None = None
    priority: int | None = Field(default=None, ge=1, le=3)
    assignee_id: int | None = None
    tags: list[str] | None = Field(default=None, max_length=10)

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str] | None) -> list[str] | None:
        return _normalize_tags(value)


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    status: TaskStatus
    priority: int
    due_date: date | None
    project_id: int
    assignee: UserBrief | None
    tags: list[str]
    created_at: datetime
    updated_at: datetime
    notification_job_id: str | None = Field(
        default=None, description="id задачи Celery, если исполнителю отправлено уведомление"
    )

    @field_validator("tags", mode="before")
    @classmethod
    def tag_names(cls, value: Any) -> list[str]:
        return [getattr(tag, "name", tag) for tag in value]
