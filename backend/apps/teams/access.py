from django.http import HttpRequest

from apps.identity_access.api.dependencies import AccessTokenAuth
from apps.organizations.access import is_platform_admin
from apps.teams.models import Team


def _has_captain_role(request: HttpRequest, user) -> bool:
    """Checks whether the user captains at least one team."""
    return is_platform_admin(user) or Team.objects.filter(captain=user).exists()


captain_auth = AccessTokenAuth(
    permission_check=_has_captain_role,
    forbidden_message="Captain access is required",
)
