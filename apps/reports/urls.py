from django.urls import path
from .views import ReportCatalogueAPIView, ReportGenerateAPIView

urlpatterns = [
    path("reports/catalogue/", ReportCatalogueAPIView.as_view(), name="report-catalogue"),
    path("reports/<slug:report_key>/", ReportGenerateAPIView.as_view(), name="report-generate"),
]
