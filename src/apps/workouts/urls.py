from django.urls import path

from .views import (
    ExerciseCandidateReviewActionView,
    ExerciseListView,
    ExerciseMediaCreateView,
    ExerciseToggleActiveView,
    ExerciseUpdateView,
    WorkoutChallengeDayCompletionCreateView,
    WorkoutPlanAssignmentStateView,
    WorkoutPlanAssignView,
    WorkoutPlanCloneView,
    WorkoutPlanComposeTemplateView,
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
    path(
        "exercises/<int:exercise_id>/media/add/",
        ExerciseMediaCreateView.as_view(),
        name="exercise_media_add",
    ),
    path(
        "exercise-candidates/<int:candidate_id>/review/",
        ExerciseCandidateReviewActionView.as_view(),
        name="exercise_candidate_review",
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
    path(
        "<slug:slug>/challenge-completion/add/",
        WorkoutChallengeDayCompletionCreateView.as_view(),
        name="challenge_completion_add",
    ),
    path(
        "<slug:slug>/compose/",
        WorkoutPlanComposeTemplateView.as_view(),
        name="compose_template",
    ),
    path("<slug:slug>/assign/", WorkoutPlanAssignView.as_view(), name="assign"),
    path(
        "<slug:slug>/assignments/<int:assignment_id>/state/",
        WorkoutPlanAssignmentStateView.as_view(),
        name="assignment_state",
    ),
]
