from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class SpotterUserAdmin(UserAdmin):
    list_display = (
        "username",
        "email",
        "display_name",
        "is_staff",
        "is_superuser",
        "is_active",
    )
    search_fields = ("username", "email", "display_name")
    fieldsets = UserAdmin.fieldsets + (("Profile", {"fields": ("display_name",)}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("Profile", {"fields": ("display_name",)}),)
