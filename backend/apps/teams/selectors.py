from django.db.models import Prefetch, QuerySet

from apps.teams.models import EntryPlayer, Player, Team, TournamentEntry
from apps.tournaments.models import Tournament
from apps.tournaments.selectors import PUBLIC_STATUSES


def public_team(team_id: int) -> Team | None:
    """Ищет команду с принятым участием в публичном турнире"""
    visible_entries = TournamentEntry.objects.filter(
        status=TournamentEntry.Status.ACCEPTED,
        tournament__visibility=Tournament.Visibility.PUBLIC,
        tournament__status__in=PUBLIC_STATUSES,
    ).select_related("tournament")
    return (
        Team.objects.filter(pk=team_id, entries__in=visible_entries)
        .select_related("captain")
        .prefetch_related(
            Prefetch("entries", queryset=visible_entries, to_attr="public_entries")
        )
        .first()
    )


def public_player(player_id: int) -> Player | None:
    """Ищет игрока, участвующего в публичном составе"""
    visible_memberships: QuerySet[EntryPlayer] = (
        EntryPlayer.objects.filter(
            status=EntryPlayer.Status.ACTIVE,
            entry__status=TournamentEntry.Status.ACCEPTED,
            entry__tournament__visibility=Tournament.Visibility.PUBLIC,
            entry__tournament__status__in=PUBLIC_STATUSES,
        )
        .select_related("entry__team", "entry__tournament")
        .order_by("entry__tournament__starts_on", "entry__tournament_id", "entry_id")
    )
    return (
        Player.objects.filter(pk=player_id, entry_memberships__in=visible_memberships)
        .prefetch_related(
            Prefetch(
                "entry_memberships",
                queryset=visible_memberships,
                to_attr="public_memberships",
            )
        )
        .first()
    )
