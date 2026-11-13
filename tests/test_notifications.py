"""Модуль notifications: Celery-задачи, подключённые к реальным действиям.

В тестах включён task_always_eager: задача выполняется сразу, без Redis и воркера.
Настоящая асинхронность (ответ мгновенно, задача в воркере) проверяется в docker compose.
"""

from unittest.mock import patch

from app.modules.notifications import tasks
from tests.helpers import auth, create_project, create_task


def messages(client, user, **params) -> list[str]:
    r = client.get("/notifications", params=params, headers=auth(user))
    assert r.status_code == 200
    return [n["message"] for n in r.json()]


def test_register_queues_welcome_notification(client):
    with patch.object(tasks.send_welcome, "delay", wraps=tasks.send_welcome.delay) as delay:
        r = client.post("/auth/register", json={"email": "new@example.com", "password": "Password123"})
    delay.assert_called_once_with(r.json()["id"])

    from tests.helpers import token_for

    msgs = messages(client, {"token": token_for("new@example.com")})
    assert len(msgs) == 1 and "Добро пожаловать" in msgs[0]


def test_assigning_task_calls_delay_and_creates_notification(client, alice, bob):
    project = create_project(client, alice, "Сайт")
    with patch.object(tasks.task_assigned, "delay", wraps=tasks.task_assigned.delay) as delay:
        task = create_task(client, alice, project["id"], title="Сверстать меню", assignee_id=bob["id"])

    delay.assert_called_once_with(task["id"])  # задача поставлена через .delay()
    assert task["notification_job_id"]
    assert "Вам назначена задача «Сверстать меню» в проекте «Сайт»" in messages(client, bob)


def test_task_without_assignee_does_not_notify(client, alice):
    project = create_project(client, alice)
    with patch.object(tasks.task_assigned, "delay") as delay:
        task = create_task(client, alice, project["id"])
    delay.assert_not_called()
    assert task["notification_job_id"] is None


def test_reassign_notifies_new_assignee(client, alice, bob):
    project = create_project(client, alice)
    task = create_task(client, alice, project["id"], title="T")
    r = client.patch(f"/tasks/{task['id']}", json={"assignee_id": bob["id"]}, headers=auth(alice))
    assert r.json()["notification_job_id"]
    assert any("Вам назначена задача «T»" in m for m in messages(client, bob))

    # повторное сохранение без смены исполнителя — без нового уведомления
    with patch.object(tasks.task_assigned, "delay") as delay:
        client.patch(f"/tasks/{task['id']}", json={"assignee_id": bob["id"]}, headers=auth(alice))
    delay.assert_not_called()


def test_completed_task_notifies_owner(client, alice, bob):
    project = create_project(client, alice, "Сайт")
    task = create_task(client, alice, project["id"], title="T", assignee_id=bob["id"])
    r = client.patch(f"/tasks/{task['id']}", json={"status": "done"}, headers=auth(bob))
    assert r.status_code == 200
    assert any(f"{bob['email']} выполнил задачу «T»" in m for m in messages(client, alice))


def test_job_status_success_with_result(client, alice, bob):
    project = create_project(client, alice)
    task = create_task(client, alice, project["id"], assignee_id=bob["id"])
    r = client.get(f"/notifications/jobs/{task['notification_job_id']}", headers=auth(alice))
    body = r.json()
    assert r.status_code == 200
    assert body["status"] == "SUCCESS" and body["ready"] is True
    assert body["result"]["delivered"] is True
    assert body["result"]["to"] == bob["email"]


def test_job_status_pending_for_unknown_id(client, alice):
    body = client.get("/notifications/jobs/00000000-0000-0000-0000-000000000000", headers=auth(alice)).json()
    assert body["status"] == "PENDING" and body["ready"] is False and body["result"] is None


def test_mark_read_and_unread_filter(client, alice, bob):
    project = create_project(client, alice)
    create_task(client, alice, project["id"], assignee_id=bob["id"])
    notifications = client.get("/notifications", headers=auth(bob)).json()
    assigned = next(n for n in notifications if "назначена" in n["message"])

    r = client.post(f"/notifications/{assigned['id']}/read", headers=auth(bob))
    assert r.status_code == 200 and r.json()["is_read"] is True
    assert all("назначена" not in m for m in messages(client, bob, unread="true"))

    # чужое уведомление — 404
    assert client.post(f"/notifications/{assigned['id']}/read", headers=auth(alice)).status_code == 404


def test_broker_down_does_not_break_request(client, alice, bob):
    project = create_project(client, alice)
    with patch.object(tasks.task_assigned, "delay", side_effect=ConnectionError("redis down")):
        r = client.post(
            f"/projects/{project['id']}/tasks", json={"title": "x", "assignee_id": bob["id"]}, headers=auth(alice)
        )
    assert r.status_code == 201
    assert r.json()["notification_job_id"] is None


def test_notifications_require_auth(client):
    assert client.get("/notifications").status_code == 401
    assert client.get("/notifications/jobs/x").status_code == 401
