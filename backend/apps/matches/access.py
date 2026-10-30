from django.http import HttpRequest
from ninja.errors import HttpError

from apps.identity_access.api.dependencies import AccessTokenAuth
from apps.matches.models import Match, MatchOfficial
from apps.organizations.access import is_platform_admin
from apps.tournaments.access import has_tournament_access, tournament_organizer_auth


def _has_judge_role(request: HttpRequest, user) -> bool:
    """Проверяет, назначен ли пользователь хотя бы на один матч."""
    return is_platform_admin(user) or MatchOfficial.objects.filter(official=user).exists()


judge_auth = AccessTokenAuth(
    permission_check=_has_judge_role,
    forbidden_message="Judge access is required",
)
organizer_auth = tournament_organizer_auth


def require_judge_match(request: HttpRequest, match_id: int) -> None:
    """Требуется официальное назначение на запрашиваемый матч."""
    match = Match.objects.filter(pk=match_id).only("id").first()
    if match is None:
        raise HttpError(404, "Match not found")
    if (
        is_platform_admin(request.auth)
        or MatchOfficial.objects.filter(match_id=match_id, official=request.auth).exists()
    ):
        return
    raise HttpError(403, "Judge assignment to this match is required")


def require_lease_takeover(request: HttpRequest, match_id: int) -> None:
    """Перехват управления разрешён только главному судье или организатору турнира."""
    match = Match.objects.select_related("tournament").filter(pk=match_id).first()
    if match is None:
        raise HttpError(404, "Match not found")
    if has_tournament_access(request.auth, match.tournament):
        return
    if MatchOfficial.objects.filter(
        match_id=match_id,
        official=request.auth,
        role=MatchOfficial.Role.REFEREE,
    ).exists():
        return
    raise HttpError(
        403,
        "Only the main referee or a tournament organizer can take over the lease",
    )


def require_organizer_match(request: HttpRequest, match_id: int) -> None:
    """Проверяет разрешение организатора, унаследованное от турнира, к которому относится матч."""
    match = Match.objects.select_related("tournament").filter(pk=match_id).first()
    if match is None:
        raise HttpError(404, "Match not found")
    if not has_tournament_access(request.auth, match.tournament):
        raise HttpError(403, "Organizer access to this match is required")
