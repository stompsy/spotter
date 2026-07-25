from django.contrib import admin

from .models import NotificationEvent


@admin.register(NotificationEvent)
class NotificationEventAdmin(admin.ModelAdmin):
    list_display = ("recipient", "notification_type", "delivery_status", "subject", "created_at")
    list_filter = ("notification_type", "delivery_status")
    search_fields = ("recipient__username", "recipient__email", "subject", "body")
