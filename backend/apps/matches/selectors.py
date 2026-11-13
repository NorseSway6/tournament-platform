from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.db.models import Exists, F, Max, OuterRef, Prefetch, Q, QuerySet
from django.utils import timezone as django_timezone

from apps.matches.access import can_view_match
from apps.matches.models import Match, MatchEvent
from apps.teams.models import TournamentEntry
from apps.tournaments.models import Tournament
from apps.tournaments.selectors import PUBLIC_STATUSES

_MATCH_LIST_RELATED = (
    "tournament__organization",
    "stage",
    "round",
    "group",
    "venue",
    "home_entry__team",
    "away_entry__team",
)


def _match_queryset() -> QuerySet[Match]:
    """Возвращает матчи с предзагруженными связями для списков и карточек."""
    return Match.objects.select_related(*_MATCH_LIST_RELATED)


def _public_match_queryset() -> QuerySet[Match]:
    """Возвращает только матчи турниров, доступных публичному API."""
    return (
        _match_queryset()
        .filter(
            tournament__status__in=PUBLIC_STATUSES,
            tournament__visibility=Tournament.Visibility.PUBLIC,
        )
        .filter(
            (Q(home_entry__isnull=True) | Q(home_entry__status=TournamentEntry.Status.ACCEPTED))
            & (Q(away_entry__isnull=True) | Q(away_entry__status=TournamentEntry.Status.ACCEPTED))
        )
    )


def _apply_match_filters(
    queryset: QuerySet[Match],
    *,
    status: str | None = None,
    team_id: int | None = None,
    stage_id: int | None = None,
    round_id: int | None = None,
    group_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> QuerySet[Match]:
    """Применяет общие фильтры списка матчей."""
    if status is not None:
        queryset = queryset.filter(status=status)
    if team_id is not None:
        queryset = queryset.filter(Q(home_entry__team_id=team_id) | Q(away_entry__team_id=team_id))
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
    return queryset


def _order_matches(queryset: QuerySet[Match]) -> QuerySet[Match]:
    """Сортирует матчи по времени и положению в сетке для стабильной пагинации."""
    return queryset.order_by(
        F("scheduled_at").asc(nulls_last=True),
        "stage__ord",
        "round__ord",
        "id",
    )


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

    queryset = _public_match_queryset()
    if tournament_id is not None:
        queryset = queryset.filter(tournament_id=tournament_id)
    queryset = _apply_match_filters(
        queryset,
        status=status,
        team_id=team_id,
        stage_id=stage_id,
        round_id=round_id,
        group_id=group_id,
        date_from=date_from,
        date_to=date_to,
    )
    return _order_matches(queryset)


def organizer_matches(
    tournament_id: int,
    *,
    status: str | None = None,
    team_id: int | None = None,
    stage_id: int | None = None,
    round_id: int | None = None,
    group_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> QuerySet[Match]:
    """Возвращает все матчи турнира для организатора, включая черновики."""
    queryset = _match_queryset().filter(tournament_id=tournament_id)
    queryset = _apply_match_filters(
        queryset,
        status=status,
        team_id=team_id,
        stage_id=stage_id,
        round_id=round_id,
        group_id=group_id,
        date_from=date_from,
        date_to=date_to,
    )
    return _order_matches(queryset)


def _with_events(queryset: QuerySet[Match]) -> QuerySet[Match]:
    """Предзагружает ленту событий в атрибут ``public_events`` для схемы матча."""
    voids = MatchEvent.objects.filter(
        match_id=OuterRef("match_id"),
        type=MatchEvent.Type.VOID,
        target_event_id=OuterRef("pk"),
    )
    events = (
        MatchEvent.objects.annotate(voided=Exists(voids))
        .select_related("player__player", "related_player__player")
        .order_by("seq")
    )
    return queryset.prefetch_related(Prefetch("events", queryset=events, to_attr="public_events"))


def get_public_match(match_id: int) -> Match | None:
    """Ищет публичный матч и заранее загружает его ленту событий"""
    return _with_events(_public_match_queryset()).filter(pk=match_id).first()


def get_organizer_match(match_id: int) -> Match | None:
    """Возвращает матч организатору независимо от видимости турнира."""
    return _with_events(_match_queryset()).filter(pk=match_id).first()


def get_match_for_viewer(match_id: int, user=None) -> Match | None:
    """Возвращает публичный матч или матч, доступный судье/организатору."""
    public_match = get_public_match(match_id)
    if public_match is not None:
        return public_match
    match = get_organizer_match(match_id)
    if match is None or not can_view_match(user, match):
        return None
    return match


def get_match(match_id: int) -> Match | None:
    """Ищет матч по идентификатору для защищаемого бизнес-среза."""
    return Match.objects.filter(pk=match_id).first()


def get_match_event_feed(match_id: int, after_seq: int, user=None) -> dict | None:
    """Возвращает события матча после sequence, если он доступен пользователю."""
    match = Match.objects.filter(pk=match_id).select_related("tournament").first()
    if match is None:
        return None
    if not _public_match_queryset().filter(pk=match_id).exists() and not can_view_match(
        user, match
    ):
        return None
    events = MatchEvent.objects.filter(match_id=match_id)
    last_seq = events.aggregate(last_seq=Max("seq"))["last_seq"] or 0
    voids = MatchEvent.objects.filter(
        match_id=OuterRef("match_id"),
        type=MatchEvent.Type.VOID,
        target_event_id=OuterRef("pk"),
    )
    items = (
        events.filter(seq__gt=after_seq)
        .annotate(voided=Exists(voids))
        .select_related("player__player", "related_player__player")
        .order_by("seq")
    )
    return {"match_id": match_id, "after_seq": after_seq, "last_seq": last_seq, "items": items}


UTC = ZoneInfo("UTC")


def parse_timezone_name(name: str | None) -> ZoneInfo:
    """Возвращает IANA-пояс или UTC, отклоняя неизвестные значения."""
    if name is None:
        return UTC
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise ValueError("timezone must be a valid IANA timezone name") from error


def local_day_bounds(day: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    """Возвращает UTC-границы локального дня [начало, следующий день)."""
    start = datetime.combine(day, time.min, tzinfo=tz)
    end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=tz)
    return start, end


def public_matches_for_local_date(
    match_date: date, timezone_name: str | None = None
) -> QuerySet[Match]:
    """Возвращает публичные матчи локального дня в указанном поясе (по умолчанию UTC)."""
    tz = parse_timezone_name(timezone_name)
    start, end = local_day_bounds(match_date, tz)
    return public_matches().filter(scheduled_at__gte=start, scheduled_at__lt=end)


def _match_list_queryset(match_ids: set[int] | None, captain_id: int | None) -> QuerySet[Match]:
    """Собирает базовый queryset для списков матчей судьи и капитана."""
    queryset = Match.objects.all()
    if match_ids is not None:
        queryset = queryset.filter(pk__in=match_ids)
    if captain_id is not None:
        queryset = queryset.filter(
            Q(home_entry__team__captain_id=captain_id) | Q(away_entry__team__captain_id=captain_id)
        )
    return queryset.select_related(*_MATCH_LIST_RELATED).order_by("scheduled_at", "id")


def _organization_timezone(name: str) -> ZoneInfo:
    """Возвращает пояс организации, подменяя некорректное значение на UTC."""
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return UTC


def _matches_for_organization_local_date(
    queryset: QuerySet[Match], match_date: date | None
) -> list[Match]:
    """Фильтрует матчи по локальной дате их организации.

    ``match_date=None`` означает «сегодня» в поясе каждой организации.
    """
    if match_date is None:
        server_today = django_timezone.localdate()
        window_start = datetime.combine(server_today - timedelta(days=1), time.min, tzinfo=UTC)
        window_end = datetime.combine(server_today + timedelta(days=2), time.min, tzinfo=UTC)
    else:
        window_start = datetime.combine(match_date - timedelta(days=1), time.min, tzinfo=UTC)
        window_end = datetime.combine(match_date + timedelta(days=2), time.min, tzinfo=UTC)
    candidates = queryset.filter(scheduled_at__gte=window_start, scheduled_at__lt=window_end)
    matches = []
    for match in candidates:
        tz = _organization_timezone(match.tournament.organization.timezone)
        local_date = match.scheduled_at.astimezone(tz).date()
        target_date = match_date or django_timezone.localdate(timezone=tz)
        if local_date == target_date:
            matches.append(match)
    return matches


def assigned_match_ids(user_id: int) -> set[int]:
    """Возвращает все матчи, назначенные пользователю, и его активные аренды."""
    return set(
        Match.objects.filter(
            Q(official_assignments__official_id=user_id)
            | Q(
                lease_judge_id=user_id,
                lease_token__isnull=False,
                lease_expires_at__gt=django_timezone.now(),
            )
        ).values_list("id", flat=True)
    )


def matches_for_date(
    match_date: date | None,
    match_ids: set[int] | None = None,
    *,
    timezone_name: str | None = None,
) -> list[Match]:
    """Возвращает матчи дня по общему поясу или по поясам организаций."""
    queryset = _match_list_queryset(match_ids, None)
    if timezone_name is None:
        return _matches_for_organization_local_date(queryset, match_date)
    tz = parse_timezone_name(timezone_name)
    day = match_date or django_timezone.localdate(timezone=tz)
    start, end = local_day_bounds(day, tz)
    return list(queryset.filter(scheduled_at__gte=start, scheduled_at__lt=end))


def matches_for_captain_date(
    match_date: date | None,
    captain_id: int,
    *,
    timezone_name: str | None = None,
) -> list[Match]:
    """Возвращает матчи дня, в которых участвует команда указанного капитана."""
    queryset = _match_list_queryset(None, captain_id)
    if timezone_name is None:
        return _matches_for_organization_local_date(queryset, match_date)
    tz = parse_timezone_name(timezone_name)
    day = match_date or django_timezone.localdate(timezone=tz)
    start, end = local_day_bounds(day, tz)
    return list(queryset.filter(scheduled_at__gte=start, scheduled_at__lt=end))
