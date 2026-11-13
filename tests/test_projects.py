"""Модуль projects: CRUD и права владельца."""

from tests.helpers import auth, create_project, create_task


def test_create_and_get_project(client, alice):
    project = create_project(client, alice, "Мобильное приложение")
    assert project["name"] == "Мобильное приложение"
    assert project["owner"]["email"] == alice["email"]
    assert project["tasks_count"] == 0

    r = client.get(f"/projects/{project['id']}", headers=auth(alice))
    assert r.status_code == 200


def test_project_validation(client, alice):
    assert client.post("/projects", json={"name": ""}, headers=auth(alice)).status_code == 422


def test_list_shows_only_own_projects(client, alice, bob):
    create_project(client, alice, "A1")
    create_project(client, alice, "A2")
    create_project(client, bob, "B1")

    names = [p["name"] for p in client.get("/projects", headers=auth(alice)).json()]
    assert names == ["A1", "A2"]


def test_admin_sees_all_projects(client, admin, alice, bob):
    create_project(client, alice, "A1")
    create_project(client, bob, "B1")
    assert len(client.get("/projects", params={"all": "true"}, headers=auth(admin)).json()) == 2
    # обычному пользователю all=true ничего не даёт
    assert len(client.get("/projects", params={"all": "true"}, headers=auth(alice)).json()) == 1


def test_other_user_gets_403(client, alice, bob):
    project = create_project(client, alice)
    pid = project["id"]
    assert client.get(f"/projects/{pid}", headers=auth(bob)).status_code == 403
    assert client.patch(f"/projects/{pid}", json={"name": "x"}, headers=auth(bob)).status_code == 403
    assert client.delete(f"/projects/{pid}", headers=auth(bob)).status_code == 403


def test_admin_can_manage_any_project(client, admin, alice):
    project = create_project(client, alice)
    r = client.patch(f"/projects/{project['id']}", json={"name": "Переименован"}, headers=auth(admin))
    assert r.status_code == 200
    assert r.json()["name"] == "Переименован"


def test_update_partial(client, alice):
    project = create_project(client, alice)
    r = client.patch(f"/projects/{project['id']}", json={"description": "Новое"}, headers=auth(alice))
    assert r.json()["description"] == "Новое"
    assert r.json()["name"] == project["name"]


def test_not_found_404(client, alice):
    assert client.get("/projects/9999", headers=auth(alice)).status_code == 404


def test_tasks_count_and_cascade_delete(client, alice):
    project = create_project(client, alice)
    task = create_task(client, alice, project["id"])
    create_task(client, alice, project["id"])
    assert client.get(f"/projects/{project['id']}", headers=auth(alice)).json()["tasks_count"] == 2

    assert client.delete(f"/projects/{project['id']}", headers=auth(alice)).status_code == 204
    # задачи удалены вместе с проектом (связь один-ко-многим, cascade)
    assert client.get(f"/tasks/{task['id']}", headers=auth(alice)).status_code == 404


def test_projects_require_auth(client):
    assert client.get("/projects").status_code == 401
    assert client.post("/projects", json={"name": "x"}).status_code == 401
