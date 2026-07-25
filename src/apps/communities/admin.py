from django.contrib import admin

from .models import Community, CommunityInvitation, CommunityJoinRequest, CommunityMembership


@admin.register(Community)
class CommunityAdmin(admin.ModelAdmin):
    list_display = ("name", "visibility", "created_by", "is_archived", "created_at")
    list_filter = ("visibility", "is_archived")
    search_fields = ("name", "slug", "description")


@admin.register(CommunityMembership)
class CommunityMembershipAdmin(admin.ModelAdmin):
    list_display = ("community", "user", "role", "status", "joined_at")
    list_filter = ("role", "status")
    search_fields = ("community__name", "user__username", "user__email")


@admin.register(CommunityJoinRequest)
class CommunityJoinRequestAdmin(admin.ModelAdmin):
    list_display = ("community", "requested_by", "status", "reviewed_by", "created_at")
    list_filter = ("status",)
    search_fields = ("community__name", "requested_by__username", "requested_by__email")


@admin.register(CommunityInvitation)
class CommunityInvitationAdmin(admin.ModelAdmin):
    list_display = ("community", "invited_email", "created_by", "expires_at", "accepted_at")
    search_fields = ("community__name", "invited_email", "created_by__username")
