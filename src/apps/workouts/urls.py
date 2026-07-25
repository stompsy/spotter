from django.urls import path

from .views import (
    ExerciseListView,
    ExerciseToggleActiveView,
    ExerciseUpdateView,
    WorkoutPlanAssignmentStateView,
    WorkoutPlanAssignView,
    WorkoutPlanCloneView,
    WorkoutPlanDetailView,
    WorkoutPlanItemCreateView,
    WorkoutPlanListView,
    WorkoutPlanPublishToggleView,
    WorkoutPlanUpdateView,
)

app_name = "workouts"

urlpatterns = [
    path("", WorkoutPlanListView.as_view(), name="list"),
    path("exercises/", ExerciseListView.as_view(), name="exercises"),
    path("exercises/<int:exercise_id>/edit/", ExerciseUpdateView.as_view(), name="exercise_edit"),
    path(
        "exercises/<int:exercise_id>/toggle-active/",
        ExerciseToggleActiveView.as_view(),
        name="exercise_toggle_active",
    ),
    path("<slug:slug>/", WorkoutPlanDetailView.as_view(), name="detail"),
    path("<slug:slug>/edit/", WorkoutPlanUpdateView.as_view(), name="edit"),
    path("<slug:slug>/clone/", WorkoutPlanCloneView.as_view(), name="clone"),
    path(
        "<slug:slug>/publish-toggle/",
        WorkoutPlanPublishToggleView.as_view(),
        name="publish_toggle",
    ),
    path("<slug:slug>/items/add/", WorkoutPlanItemCreateView.as_view(), name="add_item"),
    path("<slug:slug>/assign/", WorkoutPlanAssignView.as_view(), name="assign"),
    path(
        "<slug:slug>/assignments/<int:assignment_id>/state/",
        WorkoutPlanAssignmentStateView.as_view(),
        name="assignment_state",
    ),
]
