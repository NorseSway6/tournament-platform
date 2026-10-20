from django.contrib.auth import get_user_model
from django.db.models import Prefetch, Q

from apps.matches.models import Match, MatchOfficial
from apps.matches.services.protocol import temporary_judge_match_ids
from apps.organizations.models import Organization
from apps.teams.models import Team, TournamentEntry
from apps.tournaments.models import Tournament
from config.temporary_ids import (
    TEMPORARY_CAPTAIN_ID,
    TEMPORARY_JUDGE_ID,
    TEMPORARY_ORGANIZER_ID,
)


def get_temporary_me() -> dict:
    """Собирает профиль и доступные ролевые области для временных ID."""
    user = get_user_model().objects.filter(pk=TEMPORARY_CAPTAIN_ID).first()
    profile = None
    if user is not None:
        profile = {
            "id": user.pk,
            "username": user.username,
            "display_name": user.display_name or user.get_full_name() or user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
        }

    teams = []
    for team in Team.objects.filter(captain_id=TEMPORARY_CAPTAIN_ID).prefetch_related(
        Prefetch(
            "entries",
            queryset=TournamentEntry.objects.select_related("tournament").order_by("id"),
        )
    ).order_by("name", "id"):
        entries = [
            {
                "id": entry.id,
                "tournament_id": entry.tournament_id,
                "tournament_name": entry.tournament.name,
                "status": entry.status,
            }
            for entry in team.entries.all()
        ]
        teams.append(
            {"id": team.id, "name": team.name, "city": team.city, "entries": entries}
        )

    organizations = []
    for organization in Organization.objects.filter(pk=TEMPORARY_ORGANIZER_ID):
        tournaments = list(
            Tournament.objects.filter(organization_id=organization.id)
            .order_by("name", "id")
            .values("id", "slug", "name", "status")
        )
        organizations.append(
            {
                "id": organization.id,
                "slug": organization.slug,
                "name": organization.name,
                "city": organization.city,
                "timezone": organization.timezone,
                "tournaments": tournaments,
            }
        )

    leased_match_ids = temporary_judge_match_ids()
    assigned_matches = (
        Match.objects.filter(
            Q(official_assignments__official_id=TEMPORARY_JUDGE_ID)
            | Q(pk__in=leased_match_ids)
        )
        .select_related("tournament")
        .distinct()
        .order_by("scheduled_at", "id")
    )
    matches = [
        {
            "id": match.id,
            "tournament_id": match.tournament_id,
            "tournament_name": match.tournament.name,
            "status": match.status,
            "scheduled_at": match.scheduled_at,
        }
        for match in assigned_matches
    ]

    return {
        "identity_mode": "temporary",
        "authenticated": False,
        "profile": profile,
        "roles": {
            "captain": {"enabled": True, "teams": teams},
            "organizer": {
                "enabled": bool(organizations),
                "organizations": organizations,
            },
            "judge": {"enabled": True, "matches": matches},
        },
    }
