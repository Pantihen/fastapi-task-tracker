from sqlalchemy import select

ADMIN = {"email": "admin@example.com", "password": "Admin12345"}
PASSWORD = "Password123"


def token_for(email: str) -> str:
    """JWT напрямую, без /auth/login — чтобы тесты не упирались в rate limit (5 входов в минуту)."""
    from app.core.database import SessionLocal
    from app.core.security import create_access_token
    from app.modules.users.models import User

    with SessionLocal() as db:
        user = db.execute(select(User).where(User.email == email)).scalar_one()
        return create_access_token(subject=str(user.id), role=user.role.value)


def register(client, email: str, password: str = PASSWORD) -> dict:
    r = client.post("/auth/register", json={"email": email, "password": password})
    assert r.status_code == 201, r.text
    body = r.json()
    return {"id": body["id"], "email": email, "token": token_for(email)}


def login(client, email: str, password: str):
    return client.post("/auth/login", data={"username": email, "password": password})


def auth(user_or_token) -> dict:
    token = user_or_token["token"] if isinstance(user_or_token, dict) else user_or_token
    return {"Authorization": f"Bearer {token}"}


def create_project(client, owner, name: str = "Сайт") -> dict:
    r = client.post("/projects", json={"name": name, "description": "Описание"}, headers=auth(owner))
    assert r.status_code == 201, r.text
    return r.json()


def create_task(client, owner, project_id: int, **fields) -> dict:
    payload = {"title": "Задача", **fields}
    r = client.post(f"/projects/{project_id}/tasks", json=payload, headers=auth(owner))
    assert r.status_code == 201, r.text
    return r.json()
