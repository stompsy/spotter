from django.contrib import admin

from .models import WorkoutLog


@admin.register(WorkoutLog)
class WorkoutLogAdmin(admin.ModelAdmin):
    list_display = ("performed_by", "community", "plan", "perceived_exertion", "completed_at")
    list_filter = ("completed_at",)
    search_fields = ("performed_by__username", "community__name", "plan__name", "notes")
