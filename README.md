# Task Tracker API

Финальный проект курса «Python для backend-разработчика»: backend трекера задач на FastAPI.

Пользователи создают **проекты**, заводят в них **задачи** с тегами, приоритетом и сроком и назначают
**исполнителей**. Исполнитель получает **уведомление**: его в фоне создаёт задача Celery. Когда исполнитель
закрывает задачу, уведомление приходит владельцу проекта.

## 🌐 Публичный адрес

| | |
|---|---|
| Приложение | **https://task-tracker-production-a4f9c33d.up.railway.app** |
| Swagger UI | https://task-tracker-production-a4f9c33d.up.railway.app/docs |
| Health-check | https://task-tracker-production-a4f9c33d.up.railway.app/health |
| Репозиторий | https://github.com/Pantihen/fastapi-task-tracker |
| CI (GitHub Actions) | https://github.com/Pantihen/fastapi-task-tracker/actions |

## Стек

FastAPI · PostgreSQL · SQLAlchemy 2.0 · Alembic · Pydantic v2 · JWT (PyJWT) · passlib/bcrypt ·
slowapi · Celery · Redis · Docker / docker compose · GitHub Actions · Railway

---

## Соответствие критериям

| Критерий | Баллы | Где в проекте |
|---|---|---|
| Модульная архитектура: ≥ 3 модуля с роутерами, сервисами и схемами | 6 | `app/modules/`: **auth, users, projects, tasks, notifications** — в каждом `router.py`, `service.py`, `schemas.py` |
| PostgreSQL + SQLAlchemy, миграции Alembic, связи между таблицами | 8 | `app/modules/*/models.py`, `migrations/versions/` (0001 — схема, 0002 — изменение схемы); связи 1:N и M:N, см. схему ниже |
| Регистрация с хешированием, JWT-вход, RBAC, CORS, rate limiting | 10 | `modules/auth` (bcrypt, OAuth2 Password Flow), `core/dependencies.py` (`get_current_user`, `require_role`), `/admin/*` только для admin; CORS и `5/minute` на `/auth/login` в `main.py` |
| Фоновая задача Celery, подключённая к реальному эндпоинту | 6 | `modules/notifications/tasks.py`: создание задачи с исполнителем, смена исполнителя, закрытие задачи и регистрация вызывают `.delay()` |
| `docker compose up --build`: приложение, БД и Redis | 5 | `Dockerfile`, `docker-compose.yml` (app, worker, db, redis), `.env.docker` |
| CI с автозапуском тестов, деплой с публичным адресом | 5 | `.github/workflows/ci.yml`, деплой на Railway (адрес выше) |

---

## Архитектура

```
app/
├── main.py                  сборка приложения: роутеры, CORS, rate limit, обработчик ошибок
├── models.py                реестр всех моделей (для Alembic и SQLAlchemy)
├── core/                    общая инфраструктура
│   ├── config.py            настройки из окружения (pydantic-settings), запрет CORS "*"
│   ├── database.py          engine, сессии, Base, TimestampMixin
│   ├── security.py          bcrypt-хеширование, выпуск и проверка JWT
│   ├── dependencies.py      get_current_user (401), require_role (403), DbSession, CurrentUser, AdminUser
│   ├── exceptions.py        доменные ошибки сервисов → HTTP-ответы
│   ├── rate_limit.py        slowapi Limiter по IP
│   └── celery_app.py        экземпляр Celery (брокер и результаты — Redis)
└── modules/                 функциональные модули
    ├── auth/                регистрация, вход                     router · service · schemas
    ├── users/               профиль, администрирование (RBAC)     router · service · schemas · models
    ├── projects/            проекты (CRUD, права владельца)        router · service · schemas · models
    ├── tasks/               задачи, теги, исполнители, фильтры     router · service · schemas · models
    ├── notifications/       уведомления + фоновые задачи Celery   router · service · schemas · models · tasks
    └── health/              /health: проверка БД и Redis
migrations/                  Alembic: env.py и версии схемы
tests/                       58 тестов pytest
```

**Слои.** Роутер принимает и проверяет запрос (Pydantic-схема), достаёт пользователя через зависимость и
вызывает сервис. Сервис содержит бизнес-логику и права доступа и работает с БД через SQLAlchemy ORM.
Про HTTP сервис не знает: он бросает `NotFoundError`, `ForbiddenError` и т.п. из `core/exceptions.py`,
а обработчик в `main.py` превращает их в ответы 404, 403 и т.д.

## Схема БД

```mermaid
erDiagram
    users ||--o{ projects : "владеет (owner_id)"
    projects ||--o{ tasks : "содержит (project_id, CASCADE)"
    users |o--o{ tasks : "исполнитель (assignee_id, SET NULL)"
    tasks }o--o{ tags : "task_tags"
    users ||--o{ notifications : "получает (user_id)"

    users { int id PK
            string email UK
            string hashed_password
            enum role "user | admin" }
    projects { int id PK
               string name
               text description
               int owner_id FK }
    tasks { int id PK
            string title
            enum status "todo | in_progress | done"
            smallint priority "1..3, миграция 0002"
            date due_date
            int project_id FK
            int assignee_id FK }
    tags { int id PK
           string name UK }
    notifications { int id PK
                    int user_id FK
                    string message
                    bool is_read }
```

Связи:
- **один-ко-многим:**
  - `users → projects` (владелец);
  - `projects → tasks`: при удалении проекта его задачи удаляются (`ON DELETE CASCADE`);
  - `users → tasks` (исполнитель): при удалении пользователя задача остаётся, а поле исполнителя становится пустым (`SET NULL`);
  - `users → notifications`.
- **многие-ко-многим:** `tasks ↔ tags` через таблицу `task_tags`. Один тег (`backend`) хранится одной строкой и привязан к любому числу задач.

### Миграции Alembic

Структуру БД создают и меняют только миграции, `create_all` в приложении нет:

| Версия | Что делает |
|---|---|
| `0001_initial_schema` | все таблицы, индексы, внешние ключи, enum-типы `user_role` и `task_status` |
| `0002_add_task_priority` | добавляет `tasks.priority` (`server_default=2` для уже существующих задач) и индекс |

```bash
alembic upgrade head          # применить все миграции
alembic downgrade -1          # откатить последнюю
alembic check                 # модели совпадают с миграциями?
alembic revision --autogenerate -m "описание"   # новая миграция по изменениям моделей
```

В Docker и на сервере `alembic upgrade head` выполняется автоматически перед стартом приложения.
В CI миграции проверяются на PostgreSQL: `upgrade head`, затем `check`, затем `downgrade base`.

---

## Права доступа

| Действие | user (владелец) | user (исполнитель) | другой user | admin |
|---|---|---|---|---|
| Создать проект | ✅ | ✅ | ✅ | ✅ |
| Смотреть, менять, удалять проект и его задачи | ✅ | — | 403 | ✅ |
| Смотреть назначенную задачу | ✅ | ✅ | 403 | ✅ |
| Менять статус задачи | ✅ | ✅ | 403 | ✅ |
| Менять остальные поля задачи | ✅ | 403 | 403 | ✅ |
| `/admin/*` (пользователи, роли, статистика) | 403 | 403 | 403 | ✅ |

## Эндпоинты

| Метод | Путь | Описание |
|---|---|---|
| GET | `/health` | статус приложения, PostgreSQL и Redis |
| POST | `/auth/register` | регистрация (+ Celery: приветственное уведомление) |
| POST | `/auth/login` | вход, OAuth2 Password Flow → JWT; **не чаще 5 раз в минуту** с одного IP |
| GET | `/users/me` | мой профиль |
| GET | `/admin/users` | 🔒 admin: пользователи (`?role=`, пагинация) |
| PATCH | `/admin/users/{id}/role` | 🔒 admin: сменить роль |
| GET | `/admin/stats` | 🔒 admin: сводка по системе |
| POST / GET | `/projects` | создать / мои проекты (admin: `?all=true` — все) |
| GET / PATCH / DELETE | `/projects/{id}` | проект (владелец или admin) |
| POST | `/projects/{id}/tasks` | создать задачу (+ Celery: уведомление исполнителю) |
| GET | `/projects/{id}/tasks` | задачи проекта: `?status=`, `?tag=`, `?assignee_id=` |
| GET | `/tasks/assigned` | мои задачи как исполнителя (по приоритету и сроку) |
| GET / PATCH / DELETE | `/tasks/{id}` | задача (исполнитель может менять только `status`) |
| GET | `/notifications` | мои уведомления (`?unread=true`) |
| POST | `/notifications/{id}/read` | отметить прочитанным |
| GET | `/notifications/jobs/{job_id}` | статус задачи Celery: PENDING / STARTED / SUCCESS |

## Фоновые задачи Celery

| Действие в API | Задача Celery | Результат |
|---|---|---|
| `POST /projects/{id}/tasks` с `assignee_id` | `notifications.task_assigned` | исполнителю: «Вам назначена задача …» |
| `PATCH /tasks/{id}` со сменой исполнителя | `notifications.task_assigned` | новому исполнителю |
| `PATCH /tasks/{id}` → `status: done` | `notifications.task_completed` | владельцу проекта: «… выполнил задачу …» |
| `POST /auth/register` | `notifications.send_welcome` | новому пользователю: приветствие |

Эндпоинт вызывает `.delay()` и отвечает сразу, за десятки миллисекунд. Воркер выполняет задачу отдельно:
ждёт `EMAIL_SEND_DELAY_SECONDS` (имитация отправки письма) и записывает уведомление в PostgreSQL.
id фоновой задачи приходит в ответе (`notification_job_id`), а её статус можно проверить через
`/notifications/jobs/{job_id}`. Если Redis недоступен, основное действие всё равно выполняется, просто без уведомления.

---

## Запуск

### Docker (одной командой)

```bash
docker compose up --build
```

| Сервис | Что это |
|---|---|
| `app` | FastAPI: при старте выполняет `alembic upgrade head`, затем запускает uvicorn на порту 8000 |
| `worker` | Celery-воркер (стартует после того, как `app` применит миграции) |
| `db` | PostgreSQL 16, данные в volume `pgdata` |
| `redis` | Redis 7: брокер и хранилище результатов Celery |

- Swagger: http://localhost:8000/docs
- Админ: `admin@example.com` / `Admin12345` (из `.env.docker`)

В `.env.docker` адреса сервисов указаны **по именам** (`@db:5432`, `redis://redis:6379`), а не через localhost:
внутри контейнера `localhost` указывает на сам контейнер.

### Без Docker

Нужны PostgreSQL и Redis на localhost.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
celery -A app.core.celery_app worker --loglevel=info    # во втором терминале
```

### Тесты

```bash
pytest -v
```

58 тестов по модулям: `test_auth`, `test_users_admin`, `test_projects`, `test_tasks`, `test_notifications`,
`test_platform` (CORS, health, миграции). Локально тесты идут на SQLite, а Celery выполняется сразу,
без брокера (`task_always_eager`). На PostgreSQL их можно запустить так:

```bash
TEST_DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/test_db pytest
```

## CI/CD

`.github/workflows/ci.yml` запускается при push и pull request в `main`:

1. **migrations + pytest (PostgreSQL):** `alembic upgrade head` → `alembic check` → `alembic downgrade base` → `pytest`.
2. **docker compose up --build (e2e):** поднимает app, worker, db и redis, проверяет `/health`, затем проходит
   сценарий «регистрация → проект → задача с исполнителем» и ждёт, пока **настоящий Celery-воркер** создаст уведомление.

После push в `main` Railway автоматически пересобирает и деплоит приложение.

## Деплой (Railway)

Приложение работает на Railway: **https://task-tracker-production-a4f9c33d.up.railway.app**

| Сервис Railway | Аналог в compose |
|---|---|
| `task-tracker`: образ из `Dockerfile` этого репозитория | `app` + `worker` (в одном контейнере: `scripts/start-web-and-worker.sh`) |
| PostgreSQL | `db`; у приложения отдельная база `task_tracker` |
| Redis | `redis`; Celery использует базы Redis 2 и 3 |

На бесплатном плане Railway число сервисов ограничено, поэтому PostgreSQL и Redis общие с другим
учебным проектом. Изоляция от него такая:
- в PostgreSQL у этого приложения отдельная **база** `task_tracker`. Её при первом старте создаёт `scripts/ensure_database.py`, дальше схему ведёт Alembic;
- в Redis у Celery отдельные **номера баз** (`CELERY_BROKER_DB=2`, `CELERY_RESULT_DB=3`);
- воркер запускается с `--without-gossip --without-mingle --without-heartbeat` и не обменивается служебными сообщениями с чужими воркерами.

Переменные приложения ссылаются на **внутренние адреса** сервисов Railway, а не на localhost:

```env
DATABASE_URL=postgresql://${{fastapi-db.PGUSER}}:${{fastapi-db.PGPASSWORD}}@${{fastapi-db.PGHOST}}:${{fastapi-db.PGPORT}}/task_tracker
REDIS_URL=${{Redis.REDIS_URL}}          # → redis://...@redis.railway.internal:6379
CELERY_BROKER_DB=2
CELERY_RESULT_DB=3
PORT=8000
CORS_ORIGINS=http://localhost:3000,https://${{RAILWAY_PUBLIC_DOMAIN}}
SECRET_KEY=<случайная строка>
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=<задан в Railway, в репозитории его нет>
```

- Команда запуска: `sh scripts/start-web-and-worker.sh` (создание базы → `alembic upgrade head` → Celery-воркер + uvicorn).
- Healthcheck: `/health`.
- Каждый push в `main` запускает CI и автодеплой.

## Демонстрация через /docs

1. `POST /auth/register` — зарегистрировать двух пользователей: владельца и исполнителя.
2. **Authorize** под владельцем → `POST /projects` → `POST /projects/{id}/tasks`
   с `"assignee_id": <id исполнителя>` и `"tags": ["backend"]`. Ответ придёт сразу, с `notification_job_id`.
3. `GET /notifications/jobs/{job_id}`: сначала `STARTED`, через несколько секунд `SUCCESS`.
4. **Authorize** под исполнителем → `GET /notifications` (там уведомление о задаче), затем `GET /tasks/assigned`.
5. Исполнитель: `PATCH /tasks/{id}` с `{"status": "done"}` → 200, а с `{"title": "..."}` → **403**.
6. `GET /admin/stats` под пользователем → **403**, под админом → **200**.
7. `POST /auth/login` шесть раз подряд → шестой ответ **429**.
