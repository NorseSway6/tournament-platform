from datetime import date

from django.db.models import F, Prefetch, Q, QuerySet

from apps.matches.models import Match, MatchEvent
from apps.tournaments.models import Tournament
from apps.tournaments.selectors import PUBLIC_STATUSES
from apps.teams.models import TournamentEntry


def public_matches(
    *,
    tournament_id: int | None = None,
    status: str | None = None,
    team_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> QuerySet[Match]:
    """Возвращает публичные матчи с фильтрами и предзагруженными связями"""

    queryset = Match.objects.filter(
        tournament__status__in=PUBLIC_STATUSES,
        tournament__visibility=Tournament.Visibility.PUBLIC,
    ).filter(
        (
            Q(home_entry__isnull=True)
            | Q(home_entry__status=TournamentEntry.Status.ACCEPTED)
        )
        & (
            Q(away_entry__isnull=True)
            | Q(away_entry__status=TournamentEntry.Status.ACCEPTED)
        )
    )
    if tournament_id is not None:
        queryset = queryset.filter(tournament_id=tournament_id)
    if status is not None:
        queryset = queryset.filter(status=status)
    if team_id is not None:
        queryset = queryset.filter(
            Q(home_entry__team_id=team_id) | Q(away_entry__team_id=team_id)
        )
    if date_from is not None:
        queryset = queryset.filter(scheduled_at__date__gte=date_from)
    if date_to is not None:
        queryset = queryset.filter(scheduled_at__date__lte=date_to)

    return queryset.select_related(
        "tournament",
        "stage",
        "round",
        "venue",
        "home_entry__team",
        "away_entry__team",
    ).order_by(
        F("scheduled_at").asc(nulls_last=True),
        "stage__ord",
        "round__ord",
        "id",
    )


def get_public_match(match_id: int) -> Match | None:
    """Ищет публичный матч и заранее загружает его ленту событий"""
    events = MatchEvent.objects.select_related("player__player").order_by("seq")
    return (
        public_matches()
        .filter(pk=match_id)
        .prefetch_related(Prefetch("events", queryset=events, to_attr="public_events"))
        .first()
    )
