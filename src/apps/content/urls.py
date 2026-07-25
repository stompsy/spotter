from django.urls import path

from .views import (
    GuidanceDetailView,
    GuidanceListView,
    GuidanceModerateView,
    GuidancePublishView,
    GuidanceSubmitView,
    GuidanceUpdateView,
)

app_name = "guidance"

urlpatterns = [
    path("", GuidanceListView.as_view(), name="list"),
    path("<int:guidance_id>/", GuidanceDetailView.as_view(), name="detail"),
    path("<int:guidance_id>/edit/", GuidanceUpdateView.as_view(), name="edit"),
    path("<int:guidance_id>/submit/", GuidanceSubmitView.as_view(), name="submit"),
    path("<int:guidance_id>/moderate/", GuidanceModerateView.as_view(), name="moderate"),
    path("<int:guidance_id>/publish/", GuidancePublishView.as_view(), name="publish"),
]
