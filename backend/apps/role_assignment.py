from django.db.models import Prefetch, Q

from apps.identity_access.models import User
from apps.identity_access.selectors import get_me_profile
from apps.matches.models import Match
from apps.matches.services.protocol import judge_match_ids
from apps.organizations.models import Organization, OrganizationMember
from apps.teams.models import Team, TournamentEntry
from apps.tournaments.models import Tournament, TournamentMember


def get_me(user_id: int) -> dict:
    """Формирует контексты ролей для аутентифицированного пользователя."""
    user = User.objects.get(pk=user_id)
    is_admin = user.is_superuser or user.is_platform_admin

    teams = []
    for team in (
        Team.objects.filter(captain_id=user_id)
        .prefetch_related(
            Prefetch(
                "entries",
                queryset=TournamentEntry.objects.select_related("tournament").order_by("id"),
            )
        )
        .order_by("name", "id")
    ):
        teams.append(
            {
                "id": team.id,
                "name": team.name,
                "city": team.city,
                "entries": [
                    {
                        "id": entry.id,
                        "tournament_id": entry.tournament_id,
                        "tournament_name": entry.tournament.name,
                        "status": entry.status,
                    }
                    for entry in team.entries.all()
                ],
            }
        )

    organization_ids = set(
        OrganizationMember.objects.filter(
            user_id=user_id, role=OrganizationMember.Role.ORGANIZER
        ).values_list("organization_id", flat=True)
    )
    tournament_ids = set(
        TournamentMember.objects.filter(
            user_id=user_id, role=TournamentMember.Role.ORGANIZER
        ).values_list("tournament_id", flat=True)
    )
    if is_admin:
        org_rows = list(Organization.objects.order_by("name", "id"))
        accessible_tournaments = Tournament.objects.select_related("organization").order_by(
            "name", "id"
        )
    else:
        organization_ids.update(
            Tournament.objects.filter(pk__in=tournament_ids).values_list(
                "organization_id", flat=True
            )
        )
        org_rows = list(Organization.objects.filter(pk__in=organization_ids).order_by("name", "id"))
        accessible_tournaments = (
            Tournament.objects.select_related("organization")
            .filter(Q(organization_id__in=organization_ids) | Q(pk__in=tournament_ids))
            .distinct()
            .order_by("name", "id")
        )
    tournaments_by_org: dict[int, list[dict]] = {}
    for tournament in accessible_tournaments:
        tournaments_by_org.setdefault(tournament.organization_id, []).append(
            {
                "id": tournament.id,
                "slug": tournament.slug,
                "name": tournament.name,
                "status": tournament.status,
            }
        )
    organizations = [
        {
            "id": organization.id,
            "slug": organization.slug,
            "name": organization.name,
            "city": organization.city,
            "timezone": organization.timezone,
            "tournaments": tournaments_by_org.get(organization.id, []),
        }
        for organization in org_rows
    ]

    assigned_match_ids = Match.objects.filter(
        official_assignments__official_id=user_id
    ).values_list("pk", flat=True)
    match_ids = set(assigned_match_ids) | set(judge_match_ids(user_id))
    matches_queryset = Match.objects.filter(pk__in=match_ids)
    if is_admin:
        matches_queryset = Match.objects.all()
    matches = [
        {
            "id": match.id,
            "tournament_id": match.tournament_id,
            "tournament_name": match.tournament.name,
            "status": match.status,
            "scheduled_at": match.scheduled_at,
        }
        for match in matches_queryset.select_related("tournament").order_by("scheduled_at", "id")
    ]

    return {
        "authenticated": True,
        "profile": get_me_profile(user_id),
        "roles": {
            "captain": {"enabled": bool(teams), "teams": teams},
            "organizer": {
                "enabled": bool(organizations),
                "organizations": organizations,
            },
            "judge": {"enabled": bool(matches), "matches": matches},
            "admin": {"enabled": is_admin},
        },
    }
