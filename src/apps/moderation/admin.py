from django.contrib import admin

from .models import ModerationRecord


@admin.register(ModerationRecord)
class ModerationRecordAdmin(admin.ModelAdmin):
    list_display = ("target_type", "target_id", "decision", "decided_by", "decided_at")
    list_filter = ("decision",)
    search_fields = ("target_type", "target_id", "decided_by__username", "reason")
