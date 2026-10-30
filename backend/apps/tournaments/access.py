from django.http import HttpRequest
from ninja.errors import HttpError

from apps.identity_access.api.dependencies import AccessTokenAuth
from apps.organizations.access import is_platform_admin
from apps.organizations.models import OrganizationMember
from apps.tournaments.models import Group, Round, Stage, Tournament, TournamentMember


def _has_tournament_organizer_role(request: HttpRequest, user) -> bool:
    """Checks for any organization or tournament organizer scope."""
    return (
        is_platform_admin(user)
        or OrganizationMember.objects.filter(
            user=user, role=OrganizationMember.Role.ORGANIZER
        ).exists()
        or TournamentMember.objects.filter(user=user, role=TournamentMember.Role.ORGANIZER).exists()
    )


tournament_organizer_auth = AccessTokenAuth(
    permission_check=_has_tournament_organizer_role,
    forbidden_message="Organizer access is required",
)


def has_tournament_access(user, tournament: Tournament) -> bool:
    """Checks direct tournament membership or inherited organization access."""
    return bool(
        is_platform_admin(user)
        or OrganizationMember.objects.filter(
            user=user,
            organization_id=tournament.organization_id,
            role=OrganizationMember.Role.ORGANIZER,
        ).exists()
        or TournamentMember.objects.filter(
            user=user,
            tournament=tournament,
            role=TournamentMember.Role.ORGANIZER,
        ).exists()
    )


def require_organizer_organization_access(request: HttpRequest, organization_id: int) -> None:
    """Checks an organization scope before listing or creating its tournaments."""
    from apps.organizations.models import Organization

    if not Organization.objects.filter(pk=organization_id).exists():
        raise HttpError(404, "Organization not found")
    if (
        is_platform_admin(request.auth)
        or OrganizationMember.objects.filter(
            user=request.auth,
            organization_id=organization_id,
            role=OrganizationMember.Role.ORGANIZER,
        ).exists()
    ):
        return
    raise HttpError(403, "Organizer access to this organization is required")


def require_organizer_tournament(request: HttpRequest, tournament_id: int) -> None:
    """Checks tournament access with organization permission inherited downward."""
    tournament = Tournament.objects.filter(pk=tournament_id).first()
    if tournament is None:
        raise HttpError(404, "Tournament not found")
    if not has_tournament_access(request.auth, tournament):
        raise HttpError(403, "Organizer access to this tournament is required")


def require_organizer_stage(request: HttpRequest, stage_id: int) -> None:
    """Checks a stage through its parent tournament."""
    stage = Stage.objects.filter(pk=stage_id).only("tournament_id").first()
    if stage is None:
        raise HttpError(404, "Stage not found")
    require_organizer_tournament(request, stage.tournament_id)


def require_organizer_group(request: HttpRequest, group_id: int) -> None:
    """Checks a group through its parent stage and tournament."""
    group = Group.objects.filter(pk=group_id).only("stage_id").first()
    if group is None:
        raise HttpError(404, "Group not found")
    require_organizer_stage(request, group.stage_id)


def require_organizer_round(request: HttpRequest, round_id: int) -> None:
    """Checks a round through its parent stage and tournament."""
    round_obj = Round.objects.filter(pk=round_id).only("stage_id").first()
    if round_obj is None:
        raise HttpError(404, "Round not found")
    require_organizer_stage(request, round_obj.stage_id)
