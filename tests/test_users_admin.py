"""Модуль users: профиль и RBAC на админских эндпоинтах."""

from tests.helpers import auth, create_project, create_task


def test_admin_endpoints_forbidden_for_user(client, alice):
    assert client.get("/admin/users", headers=auth(alice)).status_code == 403
    assert client.get("/admin/stats", headers=auth(alice)).status_code == 403
    assert client.patch(f"/admin/users/{alice['id']}/role", json={"role": "admin"}, headers=auth(alice)).status_code == 403


def test_admin_endpoints_require_token(client):
    assert client.get("/admin/users").status_code == 401


def test_admin_lists_users(client, admin, alice, bob):
    r = client.get("/admin/users", headers=auth(admin))
    assert r.status_code == 200
    emails = {u["email"] for u in r.json()}
    assert {"admin@example.com", alice["email"], bob["email"]} <= emails

    only_admins = client.get("/admin/users", params={"role": "admin"}, headers=auth(admin)).json()
    assert [u["email"] for u in only_admins] == ["admin@example.com"]


def test_admin_changes_role(client, admin, alice):
    r = client.patch(f"/admin/users/{alice['id']}/role", json={"role": "admin"}, headers=auth(admin))
    assert r.status_code == 200
    assert r.json()["role"] == "admin"
    # теперь у alice есть доступ к админке (роль читается из БД, а не из старого токена)
    assert client.get("/admin/users", headers=auth(alice)).status_code == 200


def test_admin_cannot_change_own_role(client, admin):
    me = client.get("/users/me", headers=auth(admin)).json()
    r = client.patch(f"/admin/users/{me['id']}/role", json={"role": "user"}, headers=auth(admin))
    assert r.status_code == 400


def test_change_role_unknown_user_404(client, admin):
    assert client.patch("/admin/users/9999/role", json={"role": "admin"}, headers=auth(admin)).status_code == 404


def test_admin_stats(client, admin, alice, bob):
    project = create_project(client, alice)
    create_task(client, alice, project["id"], assignee_id=bob["id"])
    create_task(client, alice, project["id"], status="done")

    stats = client.get("/admin/stats", headers=auth(admin)).json()
    assert stats["users"] == 3 and stats["admins"] == 1
    assert stats["projects"] == 1
    assert stats["tasks_by_status"] == {"todo": 1, "in_progress": 0, "done": 1}
