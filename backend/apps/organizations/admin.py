from django.contrib import admin

from apps.organizations.models import Organization


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "city", "created_at", "updated_at")
    list_filter = ("city",)
    search_fields = ("name", "slug", "city")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("name", "slug", "description", "city")}),
        ("Contacts", {"fields": ("contacts",)}),
        ("Dates", {"fields": ("created_at", "updated_at")}),
    )
