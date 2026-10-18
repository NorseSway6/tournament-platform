from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from apps.identity_access.models import User


@admin.register(User)
class PlatformUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        (
            "Football Platform",
            {"fields": ("display_name", "phone", "telegram_id", "telegram_username")},
        ),
    )
    list_display = ("username", "display_name", "email", "phone", "is_staff", "is_active")
    list_filter = ("is_staff", "is_active", "is_superuser", "groups")
    search_fields = ("username", "display_name", "email", "phone", "telegram_username")
    ordering = ("username",)
