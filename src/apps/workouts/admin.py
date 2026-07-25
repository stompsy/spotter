from django.contrib import admin

from .models import Exercise, WorkoutPlan, WorkoutPlanAssignment, WorkoutPlanItem


@admin.register(Exercise)
class ExerciseAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "is_active")
    list_filter = ("category", "is_active")
    search_fields = ("name", "slug", "description")


class WorkoutPlanItemInline(admin.TabularInline):
    model = WorkoutPlanItem
    extra = 0


@admin.register(WorkoutPlan)
class WorkoutPlanAdmin(admin.ModelAdmin):
    list_display = ("name", "community", "created_by", "is_template", "is_published", "created_at")
    list_filter = ("is_template", "is_published")
    search_fields = ("name", "slug", "community__name", "created_by__username")
    inlines = [WorkoutPlanItemInline]


@admin.register(WorkoutPlanAssignment)
class WorkoutPlanAssignmentAdmin(admin.ModelAdmin):
    list_display = ("plan", "assigned_to", "assigned_community", "starts_on", "is_active")
    list_filter = ("is_active",)
    search_fields = ("plan__name", "assigned_to__username", "assigned_community__name")
