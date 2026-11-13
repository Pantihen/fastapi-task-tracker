"""Модуль tasks: задачи, теги (многие-ко-многим), исполнители, фильтры и права."""

from tests.helpers import auth, create_project, create_task


def test_create_task_with_tags_and_assignee(client, alice, bob):
    project = create_project(client, alice)
    task = create_task(
        client,
        alice,
        project["id"],
        title="Сверстать лендинг",
        tags=["Frontend", " urgent ", "frontend"],
        assignee_id=bob["id"],
        due_date="2026-12-01",
        priority=3,
    )
    assert task["tags"] == ["frontend", "urgent"]  # нормализация и без повторов
    assert task["assignee"]["email"] == bob["email"]
    assert task["status"] == "todo"
    assert task["priority"] == 3
    assert task["project_id"] == project["id"]


def test_tags_are_shared_between_tasks(client, alice):
    """Связь многие-ко-многим: один тег у нескольких задач хранится одной строкой."""
    from sqlalchemy import func, select

    from app.core.database import SessionLocal
    from app.modules.tasks.models import Tag

    project = create_project(client, alice)
    create_task(client, alice, project["id"], tags=["backend", "api"])
    create_task(client, alice, project["id"], tags=["backend"])
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Tag)) == 2


def test_unknown_assignee_400(client, alice):
    project = create_project(client, alice)
    r = client.post(f"/projects/{project['id']}/tasks", json={"title": "x", "assignee_id": 9999}, headers=auth(alice))
    assert r.status_code == 400


def test_validation(client, alice):
    project = create_project(client, alice)
    url = f"/projects/{project['id']}/tasks"
    assert client.post(url, json={"title": ""}, headers=auth(alice)).status_code == 422
    assert client.post(url, json={"title": "x", "status": "unknown"}, headers=auth(alice)).status_code == 422
    assert client.post(url, json={"title": "x", "priority": 5}, headers=auth(alice)).status_code == 422
    assert client.post(url, json={"title": "x", "tags": [f"t{i}" for i in range(11)]}, headers=auth(alice)).status_code == 422


def test_only_owner_creates_tasks(client, alice, bob):
    project = create_project(client, alice)
    r = client.post(f"/projects/{project['id']}/tasks", json={"title": "x"}, headers=auth(bob))
    assert r.status_code == 403


def test_filters(client, alice, bob):
    project = create_project(client, alice)
    pid = project["id"]
    create_task(client, alice, pid, title="A", tags=["backend"], assignee_id=bob["id"])
    create_task(client, alice, pid, title="B", tags=["frontend"], status="done")
    create_task(client, alice, pid, title="C", tags=["backend"], status="in_progress")
    url = f"/projects/{pid}/tasks"

    def titles(**params):
        return [t["title"] for t in client.get(url, params=params, headers=auth(alice)).json()]

    assert titles() == ["A", "B", "C"]
    assert titles(status="done") == ["B"]
    assert titles(tag="BACKEND") == ["A", "C"]
    assert titles(assignee_id=bob["id"]) == ["A"]
    assert titles(tag="backend", status="in_progress") == ["C"]


def test_assigned_list_sorted_by_priority(client, alice, bob):
    project = create_project(client, alice)
    create_task(client, alice, project["id"], title="low", priority=1, assignee_id=bob["id"])
    create_task(client, alice, project["id"], title="high", priority=3, assignee_id=bob["id"])
    create_task(client, alice, project["id"], title="not mine")

    titles = [t["title"] for t in client.get("/tasks/assigned", headers=auth(bob)).json()]
    assert titles == ["high", "low"]


def test_assignee_can_view_and_change_status_only(client, alice, bob):
    project = create_project(client, alice)
    task = create_task(client, alice, project["id"], assignee_id=bob["id"])
    url = f"/tasks/{task['id']}"

    assert client.get(url, headers=auth(bob)).status_code == 200
    r = client.patch(url, json={"status": "in_progress"}, headers=auth(bob))
    assert r.status_code == 200
    assert r.json()["status"] == "in_progress"

    assert client.patch(url, json={"title": "Взлом"}, headers=auth(bob)).status_code == 403
    assert client.delete(url, headers=auth(bob)).status_code == 403
    # но не может смотреть проект целиком
    assert client.get(f"/projects/{project['id']}/tasks", headers=auth(bob)).status_code == 403


def test_stranger_has_no_access(client, alice, bob):
    project = create_project(client, alice)
    task = create_task(client, alice, project["id"])
    assert client.get(f"/tasks/{task['id']}", headers=auth(bob)).status_code == 403
    assert client.patch(f"/tasks/{task['id']}", json={"status": "done"}, headers=auth(bob)).status_code == 403


def test_owner_updates_everything(client, alice, bob):
    project = create_project(client, alice)
    task = create_task(client, alice, project["id"], tags=["old"])
    r = client.patch(
        f"/tasks/{task['id']}",
        json={"title": "Новое", "tags": ["new", "api"], "assignee_id": bob["id"], "priority": 1},
        headers=auth(alice),
    )
    body = r.json()
    assert r.status_code == 200
    assert body["title"] == "Новое"
    assert body["tags"] == ["api", "new"]
    assert body["assignee"]["id"] == bob["id"]
    assert body["priority"] == 1


def test_null_title_rejected(client, alice):
    project = create_project(client, alice)
    task = create_task(client, alice, project["id"])
    assert client.patch(f"/tasks/{task['id']}", json={"title": None}, headers=auth(alice)).status_code == 400


def test_delete_task(client, alice):
    project = create_project(client, alice)
    task = create_task(client, alice, project["id"])
    assert client.delete(f"/tasks/{task['id']}", headers=auth(alice)).status_code == 204
    assert client.get(f"/tasks/{task['id']}", headers=auth(alice)).status_code == 404
