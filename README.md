# Madrasa Management System Backend

## Local setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
uvicorn config.asgi:application --reload
```

## API documentation

- Swagger UI: `/api/docs/`
- OpenAPI schema: `/api/schema/`
- Django health: `GET /api/v1/health/`
- FastAPI health: `/fastapi/health`
- FastAPI docs: `/fastapi/docs`

Swagger groups endpoints into these sections:

| Group          | Base endpoints                                                                                                    |
| -------------- | ----------------------------------------------------------------------------------------------------------------- |
| Authentication | `/api/v1/auth/register/`, `/login/`, `/token/refresh/`, `/token/verify/`, `/me/`, `/logout/`, `/change-password/` |
| Students       | `/api/v1/students/`                                                                                               |
| Academics      | `/api/v1/departments/`, `/classes/`, `/halaqas/`, `/api/v1/academic/subjects/`                                    |
| Staff          | `/api/v1/staff/`, `/staff-attendance/`, `/halaqa-assignments/`                                                    |
| Hifz           | `/api/v1/hifz-daily-logs/`                                                                                        |
| Hostel         | `/api/v1/hostel-wings/`, `/hostel-rooms/`, `/hostel-allocations/`, `/gate-passes/`                                |
| Exams          | `/api/v1/internal-exams/`, `/internal-exam-results/`, `/wafaq-registrations/`, `/wafaq-results/`                  |
| Finance        | `/api/v1/funds/`, `/donors/`, `/donations/`, `/student-fee-logs/`, `/student-sponsorships/`, `/expenses/`         |

## Authentication

All management endpoints require a JWT access token. First use `POST /api/v1/auth/register/` or `POST /api/v1/auth/login/`; each response includes `access` and `refresh` tokens. Authorize Swagger requests with:

```text
Bearer <your-access-token>
```

## Test suite

```powershell
python manage.py test
```

## Automated backups

Backup schedules are configured from **Dashboard → Settings → Backup**. Artifacts are stored privately under `private/backups/` by default; override this with `MADRASA_BACKUP_ROOT`.

Run the scheduler command every minute with Windows Task Scheduler or cron:

```powershell
.\.venv\Scripts\python.exe manage.py run_scheduled_backups
```

Retention can also be enforced independently:

```powershell
.\.venv\Scripts\python.exe manage.py prune_backup_artifacts
```

Only one backup per tenant runs at a time. Retained restores first create a safety backup and are audited.
