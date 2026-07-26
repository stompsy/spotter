from django.urls import path

from .views import WorkoutLogListCreateView

app_name = "progress"

urlpatterns = [
    path("logs/", WorkoutLogListCreateView.as_view(), name="logs"),
]
