from django.conf import settings
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("communities/", include("apps.communities.urls")),
    path("notifications/", include("apps.notifications.urls")),
    path("workouts/", include("apps.workouts.urls")),
    path("guidance/", include("apps.content.urls")),
    path("", include("apps.core.urls")),
]

if settings.DEBUG:
    urlpatterns += [path("__reload__/", include("django_browser_reload.urls"))]
