from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError

from apps.identity_access.models import AdminUser, TokenSession, User
from apps.matches.models import MatchOfficial
from apps.organizations.models import OrganizationMember
from apps.teams.models import Team
from apps.tournaments.models import TournamentMember


class IdentifierUserCreationForm(UserCreationForm):
    """Создаёт пользователя с хотя бы одним контактным идентификатором."""

    def clean(self):
        """Проверяет наличие email или телефона до сохранения пользователя."""
        cleaned_data = super().clean()
        if not cleaned_data.get("email") and not cleaned_data.get("phone"):
            raise ValidationError("Укажите email или телефон пользователя.")
        return cleaned_data

    def save(self, commit=True):
        """Нормализует пустые email и телефон в NULL, допустимый ограничением БД."""
        user = super().save(commit=False)
        user.email = user.email or None
        user.phone = user.phone or None
        if commit:
            user.save()
            self.save_m2m()
        return user


class PlatformUserCreationForm(IdentifierUserCreationForm):
    """Форма создания обычного пользователя."""

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "phone")


class PlatformAdminCreationForm(IdentifierUserCreationForm):
    """Форма создания администратора."""

    class Meta(UserCreationForm.Meta):
        model = AdminUser
        fields = ("username", "email", "phone")


def _user_fieldsets_without_staff() -> tuple:
    """Возвращает стандартные поля UserAdmin без управления staff-признаком"""
    return tuple(
        (
            section,
            {
                **options,
                "fields": tuple(
                    field
                    for field in options["fields"]
                    if field not in {"is_staff", "is_superuser"}
                ),
            },
        )
        for section, options in UserAdmin.fieldsets
    )


def _user_role_summary(user: User):
    """Displays unique role names without exposing their individual scopes."""
    roles = []
    if user.is_superuser or user.is_platform_admin:
        roles.append("Admin")
    if any(
        membership.role == OrganizationMember.Role.ORGANIZER
        for membership in user.organization_memberships.all()
    ) or any(user.tournament_memberships.all()):
        roles.append("Organizer")
    if any(user.captained_teams.all()):
        roles.append("Captain")
    if any(
        membership.role == OrganizationMember.Role.REFEREE
        for membership in user.organization_memberships.all()
    ) or any(user.match_official_assignments.all()):
        roles.append("Judge")
    return ", ".join(roles) if roles else "—"


def _with_role_contexts(queryset):
    """Prefetches role relations shown by the summary in admin lists."""
    return queryset.prefetch_related(
        "organization_memberships",
        "tournament_memberships",
        "captained_teams",
        "match_official_assignments",
    )


class OrganizationMembershipUserInline(admin.TabularInline):
    """Assigns the user organizer access to selected organizations."""

    model = OrganizationMember
    fk_name = "user"
    extra = 0
    autocomplete_fields = ("organization",)
    fields = ("organization", "role", "created_at")
    readonly_fields = ("created_at",)


class TournamentMembershipUserInline(admin.TabularInline):
    """Assigns the user organizer access to selected tournaments."""

    model = TournamentMember
    fk_name = "user"
    extra = 0
    autocomplete_fields = ("tournament",)
    fields = ("tournament", "role", "created_at")
    readonly_fields = ("created_at",)


class CaptainTeamUserInline(admin.TabularInline):
    """Creates or edits teams for which this user is the captain."""

    model = Team
    fk_name = "captain"
    extra = 0
    fields = ("name", "city", "created_at")
    readonly_fields = ("created_at",)


class JudgeAssignmentUserInline(admin.TabularInline):
    """Assigns this user to matches as an official and grants judge access."""

    model = MatchOfficial
    fk_name = "official"
    extra = 0
    autocomplete_fields = ("match",)
    fields = ("match", "role")


class UserRoleAssignmentAdminMixin:
    """Shows role assignment inlines only after the user record exists."""

    inlines = (
        OrganizationMembershipUserInline,
        TournamentMembershipUserInline,
        CaptainTeamUserInline,
        JudgeAssignmentUserInline,
    )

    def get_inline_instances(self, request, obj=None):
        """Avoids displaying linked-object forms on the user creation page."""
        if obj is None:
            return []
        return super().get_inline_instances(request, obj)


@admin.register(AdminUser)
class AdminUserAdmin(UserRoleAssignmentAdminMixin, UserAdmin):
    """Показывает администраторов отдельно от обычных пользователей"""

    add_form = PlatformAdminCreationForm
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("username", "email", "phone", "password1", "password2"),
            },
        ),
    )
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "email")}),
        (
            "Football Platform",
            {"fields": ("display_name", "phone", "telegram_id", "telegram_username")},
        ),
        (
            "Permissions",
            {"fields": ("is_active", "is_superuser", "groups", "user_permissions")},
        ),
        ("Roles and scopes", {"fields": ("role_summary",)}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    readonly_fields = ("is_platform_admin", "role_summary")
    list_display = (
        "id",
        "username",
        "email",
        "is_platform_admin",
        "is_superuser",
        "is_active",
        "role_summary",
    )
    list_filter = ("is_superuser", "is_active", "groups")
    search_fields = ("username", "display_name", "email", "phone")

    def get_queryset(self, request):
        """Оставляет в разделе только учетные записи с правом входа в админку"""
        return _with_role_contexts(super().get_queryset(request).filter(is_staff=True))

    @admin.display(description="Roles and scopes")
    def role_summary(self, obj):
        """Shows this user's platform and domain-scoped roles."""
        return _user_role_summary(obj)

    def save_model(self, request, obj, form, change):
        """Помечает создаваемую или редактируемую AdminUser как staff"""
        obj.is_staff = True
        obj.is_platform_admin = True
        super().save_model(request, obj, form, change)


@admin.register(User)
class PlatformUserAdmin(UserRoleAssignmentAdminMixin, UserAdmin):
    """Управляет обычными пользователями без отображения админ-аккаунтов"""

    add_form = PlatformUserCreationForm
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("username", "email", "phone", "password1", "password2"),
            },
        ),
    )
    fieldsets = (
        *_user_fieldsets_without_staff(),
        (
            "Football Platform",
            {"fields": ("display_name", "phone", "telegram_id", "telegram_username")},
        ),
        ("Roles and scopes", {"fields": ("is_platform_admin", "role_summary")}),
    )
    readonly_fields = ("role_summary",)
    list_display = (
        "username",
        "display_name",
        "email",
        "phone",
        "is_active",
        "role_summary",
    )
    list_filter = ("is_active", "groups")
    search_fields = ("username", "display_name", "email", "phone", "telegram_username")
    ordering = ("username",)

    def get_queryset(self, request):
        """Исключает записи администраторов из списка обычных пользователей"""
        return _with_role_contexts(super().get_queryset(request).filter(is_staff=False))

    @admin.display(description="Roles and scopes")
    def role_summary(self, obj):
        """Shows this user's platform and domain-scoped roles."""
        return _user_role_summary(obj)

    def save_model(self, request, obj, form, change):
        """Keeps platform account flags out of this user form."""
        obj.is_staff = False
        obj.is_superuser = False
        super().save_model(request, obj, form, change)


@admin.register(TokenSession)
class TokenSessionAdmin(admin.ModelAdmin):
    """Показывает состояние сессий, не раскрывая сами токены."""

    list_display = ("user", "created_at", "expires_at", "revoked_at")
    list_filter = ("revoked_at",)
    search_fields = ("user__username",)
    readonly_fields = (
        "id",
        "user",
        "refresh_token_hash",
        "expires_at",
        "revoked_at",
        "created_at",
    )
