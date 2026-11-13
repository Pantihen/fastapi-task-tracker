from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    message: str
    is_read: bool
    created_at: datetime


class JobStatus(BaseModel):
    """Состояние фоновой задачи Celery."""

    job_id: str
    status: str  # PENDING | STARTED | SUCCESS | FAILURE | RETRY
    ready: bool
    result: Any | None = None
    error: str | None = None
