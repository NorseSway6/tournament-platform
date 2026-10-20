from datetime import date

from django.db.models import Exists, F, Max, OuterRef, Prefetch, Q, QuerySet

from apps.matches.models import Match, MatchEvent
from apps.tournaments.models import Tournament
from apps.tournaments.selectors import PUBLIC_STATUSES
from apps.teams.models import TournamentEntry


def public_matches(
    *,
    tournament_id: int | None = None,
    status: str | None = None,
    team_id: int | None = None,
    stage_id: int | None = None,
    round_id: int | None = None,
    group_id: int | None = None,
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
    if stage_id is not None:
        queryset = queryset.filter(stage_id=stage_id)
    if round_id is not None:
        queryset = queryset.filter(round_id=round_id)
    if group_id is not None:
        queryset = queryset.filter(group_id=group_id)
    if date_from is not None:
        queryset = queryset.filter(scheduled_at__date__gte=date_from)
    if date_to is not None:
        queryset = queryset.filter(scheduled_at__date__lte=date_to)

    return queryset.select_related(
        "tournament__organization",
        "stage",
        "round",
        "group",
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
    voids = MatchEvent.objects.filter(
        match_id=OuterRef("match_id"), type=MatchEvent.Type.VOID,
        target_event_id=OuterRef("pk"),
    )
    events = MatchEvent.objects.annotate(voided=Exists(voids)).select_related(
        "player__player", "related_player__player"
    ).order_by("seq")
    return (
        public_matches()
        .filter(pk=match_id)
        .prefetch_related(Prefetch("events", queryset=events, to_attr="public_events"))
        .first()
    )


def get_match(match_id: int) -> Match | None:
    """Ищет матч по идентификатору для защищаемого бизнес-среза."""
    return Match.objects.filter(pk=match_id).first()


def get_match_event_feed(match_id: int, after_seq: int) -> dict | None:
    """Возвращает события после sequence и последний номер события матча."""
    match = Match.objects.filter(pk=match_id).only("id").first()
    if match is None:
        return None
    events = MatchEvent.objects.filter(match_id=match_id)
    last_seq = events.aggregate(last_seq=Max("seq"))["last_seq"] or 0
    voids = MatchEvent.objects.filter(
        match_id=OuterRef("match_id"), type=MatchEvent.Type.VOID,
        target_event_id=OuterRef("pk"),
    )
    items = events.filter(seq__gt=after_seq).annotate(voided=Exists(voids)).select_related(
        "player__player", "related_player__player"
    ).order_by("seq")
    return {"match_id": match_id, "after_seq": after_seq, "last_seq": last_seq, "items": items}


def matches_for_date(match_date: date, match_ids: set[int] | None = None) -> QuerySet[Match]:
    """Возвращает матчи указанного дня, при необходимости по заданным ID."""
    queryset = Match.objects.filter(scheduled_at__date=match_date)
    if match_ids is not None:
        queryset = queryset.filter(pk__in=match_ids)
    return queryset.select_related(
        "tournament__organization", "stage", "round", "group", "venue", "home_entry__team", "away_entry__team"
    ).order_by("scheduled_at", "id")


def matches_for_captain_date(match_date: date, captain_id: int) -> QuerySet[Match]:
    """Возвращает матчи дня, в которых участвует команда указанного капитана."""
    return (
        Match.objects.filter(scheduled_at__date=match_date)
        .filter(
            Q(home_entry__team__captain_id=captain_id)
            | Q(away_entry__team__captain_id=captain_id)
        )
        .select_related(
            "tournament__organization", "stage", "round", "group", "venue", "home_entry__team", "away_entry__team"
        )
        .order_by("scheduled_at", "id")
    )
