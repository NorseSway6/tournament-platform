from django.contrib import admin

from apps.organizations.models import Organization, OrganizationMember


class OrganizationMemberInline(admin.TabularInline):
    """Keeps organization-scoped organizer assignments with the organization."""

    model = OrganizationMember
    extra = 0
    autocomplete_fields = ("user",)
    fields = ("user", "role", "created_at")
    readonly_fields = ("created_at",)


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "city", "timezone", "created_at", "updated_at")
    list_filter = ("city",)
    search_fields = ("name", "slug", "city")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("created_at", "updated_at")
    inlines = (OrganizationMemberInline,)
    fieldsets = (
        (None, {"fields": ("name", "slug", "description", "city", "timezone")}),
        ("Contacts", {"fields": ("contacts",)}),
        ("Dates", {"fields": ("created_at", "updated_at")}),
    )
