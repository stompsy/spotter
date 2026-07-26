from django import forms
from django.db.models import Q

from apps.workouts.models import WorkoutPlan

from .models import WorkoutLog


class WorkoutLogForm(forms.ModelForm):
    class Meta:
        model = WorkoutLog
        fields = ["plan", "perceived_exertion", "notes"]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["plan"].required = False
        self.fields["perceived_exertion"].required = False
        self.fields["perceived_exertion"].min_value = 1
        self.fields["perceived_exertion"].max_value = 10

        if user is None:
            self.fields["plan"].queryset = WorkoutPlan.objects.none()
            return

        assigned_plan_ids = user.assigned_workout_plans.values_list("plan_id", flat=True)
        self.fields["plan"].queryset = WorkoutPlan.objects.filter(
            Q(created_by=user) | Q(id__in=assigned_plan_ids)
        ).distinct()
