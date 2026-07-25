from .models import NotificationEvent


def notifications_context(request):
    if not request.user.is_authenticated:
        return {"unread_notifications_count": 0}

    unread_count = NotificationEvent.objects.filter(
        recipient=request.user,
        read_at__isnull=True,
    ).count()
    return {"unread_notifications_count": unread_count}