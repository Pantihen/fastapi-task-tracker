from pydantic import BaseModel, EmailStr, Field

from app.modules.users.schemas import UserOut


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72, description="От 8 до 72 символов (ограничение bcrypt)")


class RegisterOut(UserOut):
    welcome_job_id: str | None = Field(
        default=None, description="id фоновой задачи Celery, которая создаёт приветственное уведомление"
    )


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
