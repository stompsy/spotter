from __future__ import annotations

from django import forms
from django.db.models import QuerySet

from apps.communities.models import Community, MembershipStatus

from .models import GuidanceContent


class GuidanceContentForm(forms.ModelForm):
    class Meta:
        model = GuidanceContent
        fields = ["title", "topic", "body", "community"]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["community"].required = False
        self.fields["community"].queryset = self._community_queryset(user)

    @staticmethod
    def _community_queryset(user) -> QuerySet[Community]:
        if not user or not user.is_authenticated:
            return Community.objects.none()
        return Community.objects.filter(
            memberships__user=user,
            memberships__status=MembershipStatus.ACTIVE,
            is_archived=False,
        ).distinct()
