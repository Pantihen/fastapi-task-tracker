from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.users.schemas import UserBrief


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    owner: UserBrief
    tasks_count: int = 0
    created_at: datetime
    updated_at: datetime
