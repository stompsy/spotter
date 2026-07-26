from django.urls import path

from .views import WorkoutLogExportCsvView, WorkoutLogListCreateView, WorkoutTrendExportCsvView

app_name = "progress"

urlpatterns = [
    path("logs/", WorkoutLogListCreateView.as_view(), name="logs"),
    path("logs/export.csv", WorkoutLogExportCsvView.as_view(), name="logs_export_csv"),
    path("trend/export.csv", WorkoutTrendExportCsvView.as_view(), name="trend_export_csv"),
]
