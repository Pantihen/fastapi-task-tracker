"""Реестр всех моделей.

Импорт этого модуля регистрирует все таблицы в Base.metadata — это нужно
Alembic (autogenerate) и SQLAlchemy (разрешение строковых relationship).
"""

from app.core.database import Base
from app.modules.notifications.models import Notification
from app.modules.projects.models import Project
from app.modules.tasks.models import Tag, Task, TaskStatus, task_tags
from app.modules.users.models import Role, User

__all__ = ["Base", "Notification", "Project", "Role", "Tag", "Task", "TaskStatus", "User", "task_tags"]
