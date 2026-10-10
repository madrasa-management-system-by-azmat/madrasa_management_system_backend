from django.urls import path
from .views import GlobalSearchAPIView

urlpatterns = [path("search/global/", GlobalSearchAPIView.as_view(), name="global-search")]
