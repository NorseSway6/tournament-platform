from datetime import date as date_type

from django.http import HttpRequest
from django.utils import timezone as django_timezone
from ninja import Query, Router
from ninja.errors import HttpError

from apps.common.api_errors import api_response
from apps.common.pagination import paginate
from apps.identity_access.api.dependencies import (
    optional_access_token_user,
    request_user_id,
)
from apps.matches.access import judge_auth, require_judge_match
from apps.matches.schemas.events import MatchEventAppendOut, MatchEventCreate, MatchEventFeedOut
from apps.matches.schemas.public import MatchDetailOut, MatchPage, TodayOut
from apps.matches.schemas.types import MatchStatus
from apps.matches.selectors import (
    get_match_event_feed,
    get_match_for_viewer,
    parse_timezone_name,
    public_matches,
    public_matches_for_local_date,
)
from apps.matches.services.protocol import append_match_event
from apps.tournaments.selectors import get_public_tournament

public_router = Router(tags=["Matches"])
matches_router = Router(tags=["Matches"])


@public_router.get(
    "/tournaments/{tournament_id}/matches",
    response=api_response(MatchPage),
    tags=["Tournament matches"],
)
def list_tournament_matches(
    request: HttpRequest,
    tournament_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: MatchStatus | None = None,
    team: int | None = Query(None, ge=1),
    date_from: date_type | None = None,
    date_to: date_type | None = None,
    stage_id: int | None = Query(None, ge=1),
    round_id: int | None = Query(None, ge=1),
    group_id: int | None = Query(None, ge=1),
):
    """Возвращает отфильтрованную страницу матчей публичного турнира."""

    tournament = get_public_tournament(tournament_id)
    if tournament is None:
        raise HttpError(404, "Tournament not found")
    if date_from and date_to and date_from > date_to:
        raise HttpError(422, "date_from must be earlier than or equal to date_to")
    queryset = public_matches(
        tournament_id=tournament.id,
        status=status,
        team_id=team,
        stage_id=stage_id,
        round_id=round_id,
        group_id=group_id,
        date_from=date_from,
        date_to=date_to,
    )
    result = paginate(queryset, page, page_size)
    return result


@matches_router.get("/{match_id}", response=api_response(MatchDetailOut))
def get_match(request: HttpRequest, match_id: int):
    """Возвращает публичный матч или матч, доступный судье/организатору."""
    match = get_match_for_viewer(match_id, optional_access_token_user(request))
    if match is None:
        raise HttpError(404, "Match not found")
    return match


@public_router.get("/today", response=api_response(TodayOut), tags=["Today"])
def today_matches(request: HttpRequest, timezone: str | None = Query(None, max_length=64)):
    """Возвращает публичные матчи текущей даты в указанном поясе (по умолчанию UTC)."""
    try:
        tz = parse_timezone_name(timezone)
    except ValueError as error:
        raise HttpError(422, str(error)) from error
    today = django_timezone.localdate(timezone=tz)
    matches = list(public_matches_for_local_date(today, timezone))
    return {
        "date": today,
        "timezone": tz.key,
        "items": matches,
        "total": len(matches),
    }


@matches_router.get("/{match_id}/events", response=api_response(MatchEventFeedOut))
def list_match_events(
    request: HttpRequest,
    match_id: int,
    after_seq: int = Query(0, ge=0),
):
    """Возвращает ленту событий после переданного номера sequence."""
    result = get_match_event_feed(match_id, after_seq, optional_access_token_user(request))
    if result is None:
        raise HttpError(404, "Match not found")
    return result


@matches_router.post(
    "/{match_id}/events",
    response=api_response({201: MatchEventAppendOut, 200: MatchEventAppendOut}),
    auth=judge_auth,
    tags=["Judge"],
)
def post_match_event(request: HttpRequest, match_id: int, payload: MatchEventCreate):
    """Добавляет или идемпотентно повторяет событие и возвращает новый счёт."""
    require_judge_match(request, match_id)
    result, created = append_match_event(match_id, request_user_id(request), payload.model_dump())
    return (201 if created else 200, result)
