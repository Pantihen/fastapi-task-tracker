"""Модуль auth: регистрация, хеширование, JWT-вход, 401, rate limiting."""

from sqlalchemy import select

from tests.helpers import ADMIN, PASSWORD, auth, login, register


def test_register_success(client):
    r = client.post("/auth/register", json={"email": "New@Example.com", "password": PASSWORD})
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "new@example.com"  # email нормализуется
    assert body["role"] == "user"
    assert "password" not in body and "hashed_password" not in body
    assert body["welcome_job_id"]


def test_password_is_hashed_with_bcrypt(client, alice):
    from app.core.database import SessionLocal
    from app.modules.users.models import User

    with SessionLocal() as db:
        user = db.execute(select(User).where(User.email == alice["email"])).scalar_one()
    assert user.hashed_password != PASSWORD
    assert user.hashed_password.startswith("$2b$")


def test_register_duplicate_409(client, alice):
    r = client.post("/auth/register", json={"email": "ALICE@example.com", "password": "Another123"})
    assert r.status_code == 409


def test_register_validation_422(client):
    assert client.post("/auth/register", json={"email": "not-an-email", "password": PASSWORD}).status_code == 422
    assert client.post("/auth/register", json={"email": "a@example.com", "password": "short"}).status_code == 422


def test_login_returns_jwt(client, alice):
    r = login(client, alice["email"], PASSWORD)
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"].count(".") == 2


def test_login_wrong_password_401(client, alice):
    assert login(client, alice["email"], "wrong-password").status_code == 401
    assert login(client, "nobody@example.com", PASSWORD).status_code == 401


def test_admin_seeded_and_can_login(client):
    r = login(client, ADMIN["email"], ADMIN["password"])
    assert r.status_code == 200


def test_protected_endpoint_401(client, alice):
    assert client.get("/users/me").status_code == 401
    assert client.get("/users/me", headers=auth("garbage.token.value")).status_code == 401
    r = client.get("/users/me", headers=auth(alice))
    assert r.status_code == 200
    assert r.json()["email"] == alice["email"]


def test_expired_token_401(client, alice):
    from app.core.security import create_access_token

    expired = create_access_token(subject=str(alice["id"]), role="user", expires_minutes=-1)
    assert client.get("/users/me", headers=auth(expired)).status_code == 401


def test_login_rate_limit_429(client, alice):
    codes = [login(client, alice["email"], "wrong-password").status_code for _ in range(6)]
    assert codes[:5] == [401] * 5
    assert codes[5] == 429


def test_sql_injection_in_login(client, alice):
    assert login(client, "' OR '1'='1", "' OR '1'='1").status_code == 401
