from django.http import HttpRequest
from ninja.errors import HttpError

from apps.identity_access.api.dependencies import AccessTokenAuth
from apps.matches.models import Match, MatchOfficial
from apps.organizations.access import is_platform_admin
from apps.tournaments.access import has_tournament_access, tournament_organizer_auth


def _has_judge_role(request: HttpRequest, user) -> bool:
    """Checks whether the user is assigned to at least one match."""
    return is_platform_admin(user) or MatchOfficial.objects.filter(official=user).exists()


judge_auth = AccessTokenAuth(
    permission_check=_has_judge_role,
    forbidden_message="Judge access is required",
)
organizer_auth = tournament_organizer_auth


def require_judge_match(request: HttpRequest, match_id: int) -> None:
    """Requires an official assignment for the requested match."""
    match = Match.objects.filter(pk=match_id).only("id").first()
    if match is None:
        raise HttpError(404, "Match not found")
    if is_platform_admin(request.auth) or MatchOfficial.objects.filter(
        match_id=match_id, official=request.auth
    ).exists():
        return
    raise HttpError(403, "Judge assignment to this match is required")


def require_organizer_match(request: HttpRequest, match_id: int) -> None:
    """Checks organizer permission inherited from the match's tournament."""
    match = Match.objects.select_related("tournament").filter(pk=match_id).first()
    if match is None:
        raise HttpError(404, "Match not found")
    if not has_tournament_access(request.auth, match.tournament):
        raise HttpError(403, "Organizer access to this match is required")
