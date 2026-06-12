from django.contrib import admin
from django.conf import settings
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("favicon.ico", RedirectView.as_view(url=f"/{settings.STATIC_URL}img/favicon-heart.svg", permanent=True)),
    path("", include("core.urls")),
]
