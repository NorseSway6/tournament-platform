from django.http import HttpRequest
from ninja.errors import HttpError

from apps.identity_access.api.dependencies import AccessTokenAuth
from apps.organizations.models import Organization, OrganizationMember


def is_platform_admin(user) -> bool:
    """Возвращает информацию о том, имеет ли учетная запись административный доступ."""
    return bool(user and (user.is_superuser or user.is_platform_admin))


def _has_organization_role(request: HttpRequest, user) -> bool:
    """Проверяет, есть ли у пользователя хотя бы одна область действия, связанная с организацией."""
    return (
        is_platform_admin(user)
        or OrganizationMember.objects.filter(
            user=user, role=OrganizationMember.Role.ORGANIZER
        ).exists()
    )


organization_organizer_auth = AccessTokenAuth(
    permission_check=_has_organization_role,
    forbidden_message="Organization organizer access is required",
)


def require_organizer_organization(request: HttpRequest, organization_id: int) -> None:
    """Проверяет область действия организации на предмет настроек и ресурсов уровня организации."""
    user = request.auth
    if is_platform_admin(user):
        return
    if OrganizationMember.objects.filter(
        user=user,
        organization_id=organization_id,
        role=OrganizationMember.Role.ORGANIZER,
    ).exists():
        return
    if not Organization.objects.filter(pk=organization_id).exists():
        raise HttpError(404, "Organization not found")
    raise HttpError(403, "Organizer access to this organization is required")


def require_organizer_organization_access(request: HttpRequest, organization_id: int) -> None:
    """Проверяет, имеет ли вызывающий членство в организации в качестве организатора."""
    require_organizer_organization(request, organization_id)
