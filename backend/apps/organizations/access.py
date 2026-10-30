from django.http import HttpRequest
from ninja.errors import HttpError

from apps.identity_access.api.dependencies import AccessTokenAuth
from apps.organizations.models import Organization, OrganizationMember


def is_platform_admin(user) -> bool:
    """Returns whether the account has platform-wide administrative access."""
    return bool(user and (user.is_superuser or user.is_platform_admin))


def _has_organization_role(request: HttpRequest, user) -> bool:
    """Checks whether the user has at least one organization scope."""
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
    """Checks organization scope for organization-level settings and resources."""
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
    """Checks that the caller has a direct organizer membership in an organization."""
    require_organizer_organization(request, organization_id)
