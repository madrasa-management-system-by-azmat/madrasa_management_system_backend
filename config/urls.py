from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView


def health_check(_request):
    return JsonResponse({"status": "ok", "service": "django-api"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/health/", health_check, name="health-check"),
    path("api/v1/auth/", include("apps.users.urls")),
    path("api/v1/", include("apps.students.urls")),
    path("api/v1/", include("apps.staff.urls")),
    path("api/v1/academic/", include("apps.academics.urls")),
    path("api/v1/", include("apps.hifz.urls")),
    path("api/v1/", include("apps.hostel.urls")),
    path("api/v1/", include("apps.exams.urls")),
    path("api/v1/", include("apps.finance.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
