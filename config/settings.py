"""Django settings for the Madrasa Management System API."""

import os
from datetime import timedelta
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "development-only-change-this-secret-key")
DEBUG = os.getenv("DJANGO_DEBUG", "true").lower() == "true"
ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",
    "apps.users",
    "apps.students",
    "apps.staff",
    "apps.academics",
    "apps.hifz",
    "apps.hostel",
    "apps.exams",
    "apps.finance",
    "apps.library",
    "apps.fatwas",
    "apps.meetings",
    "apps.tasks",
    "apps.documents",
    "apps.guardians",
    "apps.leaves",
    "apps.development",
    "apps.certificates",
    "apps.operations",
    "apps.auditlog",
    "apps.backups",
    "apps.search",
    "apps.reports",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "config.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.auditlog.middleware.AuditContextMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "ur"
TIME_ZONE = "Asia/Karachi"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
BACKUP_ROOT = Path(os.getenv("MADRASA_BACKUP_ROOT", BASE_DIR / "private" / "backups"))

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.auditlog.authentication.AuditJWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Madrasa Management System API",
    "DESCRIPTION": "REST APIs for Pakistani madrasa administration.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "TAGS": [
        {"name": "Authentication", "description": "Login, tokens, and user account endpoints."},
        {"name": "Students", "description": "Student registration and profile management."},
        {"name": "Staff", "description": "Teachers, staff attendance, and halaqa assignments."},
        {"name": "Academics", "description": "Departments, classes, subjects, and halaqas."},
        {"name": "Hifz", "description": "Daily Hifz diary and progress logs."},
        {"name": "Hostel", "description": "Wings, rooms, allocations, and gate passes."},
        {"name": "Exams", "description": "Internal exams, Wafaq registration, and results."},
        {"name": "Finance", "description": "Funds, donors, fees, sponsorships, and expenses."},
        {"name": "Library", "description": "Catalog, copies, members, circulation, reservations, and fines."},
        {"name": "Fatwas", "description": "Dar al-Ifta inquiries, research, review, approval, and publication."},
        {"name": "Meetings", "description": "Meeting schedules, participants, minutes, decisions, and action tracking."},
        {"name": "Administrative Tasks", "description": "Projects, assignments, checklists, recurring work, review, and completion tracking."},
        {"name": "Documents", "description": "Secure document repository, versions, access grants, approval, and retention."},
        {"name": "Parent Portal", "description": "Guardian accounts, linked students, parent dashboards, announcements, and parent-teacher meetings."},
        {"name": "Leave Management", "description": "Staff and student leave requests, policies, balances, approval, substitutions, and attendance integration."},
        {"name": "Student Development", "description": "Discipline, training, rewards, and alumni engagement."},
        {"name": "Certificate Verification", "description": "Issued credentials, signatures, revocation, reissue, and public verification."},
        {"name": "Operations", "description": "Store, inventory, procurement, assets, transport, and kitchen operations."},
        {"name": "Audit and Archiving", "description": "Tamper-evident audit events, archive batches, retention policies, and legal holds."},
    ],
    "SECURITY": [{"jwtAuth": []}],
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(days=7),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}
