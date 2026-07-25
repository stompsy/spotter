from django.contrib import admin

from .models import GuidanceContent


@admin.register(GuidanceContent)
class GuidanceContentAdmin(admin.ModelAdmin):
    list_display = ("title", "topic", "status", "author", "community", "submitted_at")
    list_filter = ("topic", "status")
    search_fields = ("title", "body", "author__username", "community__name")
