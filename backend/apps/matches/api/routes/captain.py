from django.http import HttpRequest
from django.utils import timezone as django_timezone
from ninja import Query, Router
from ninja.errors import HttpError

from apps.common.api_errors import api_response
from apps.identity_access.api.dependencies import request_user_id
from apps.matches.schemas.lineups import (
    LineupCheckOut,
    LineupUpdateIn,
    MatchLineupOut,
)
from apps.matches.schemas.public import TodayOut
from apps.matches.selectors import matches_for_captain_date, parse_timezone_name
from apps.matches.services.lineups import (
    check_captain_lineup,
    get_captain_match_lineup,
    submit_captain_match_lineup,
    update_captain_match_lineup,
)
from apps.teams.access import captain_auth

captain_router = Router(tags=["Captain"], auth=captain_auth)


@captain_router.get("/me/today", response=api_response(TodayOut))
def captain_today_matches(request: HttpRequest, timezone: str | None = Query(None, max_length=64)):
    """Возвращает сегодняшние матчи команд капитана, без пояса — по поясам организаций."""
    try:
        tz = parse_timezone_name(timezone)
    except ValueError as error:
        raise HttpError(422, str(error)) from error
    match_date = None if timezone is None else django_timezone.localdate(timezone=tz)
    matches = matches_for_captain_date(
        match_date,
        request_user_id(request),
        timezone_name=timezone,
    )
    return {
        "date": match_date or django_timezone.localdate(),
        "timezone": timezone,
        "items": matches,
        "total": len(matches),
    }


@captain_router.get("/matches/{match_id}/lineup", response=api_response(MatchLineupOut))
def get_captain_lineup(request: HttpRequest, match_id: int):
    """Возвращает текущий состав или предзаполненный ростер капитана."""
    return get_captain_match_lineup(request_user_id(request), match_id)


@captain_router.put("/matches/{match_id}/lineup", response=api_response(MatchLineupOut))
def put_captain_lineup(request: HttpRequest, match_id: int, payload: LineupUpdateIn):
    """Сохраняет состав капитана и комментарий как черновик."""
    data = payload.model_dump()
    return update_captain_match_lineup(
        request_user_id(request), match_id, data["players"], data["comment"]
    )


@captain_router.post("/matches/{match_id}/lineup/submit", response=api_response(LineupCheckOut))
def submit_match_lineup(request: HttpRequest, match_id: int):
    """Проверяет и отправляет состав матча на рассмотрение."""
    return submit_captain_match_lineup(request_user_id(request), match_id)


@captain_router.get("/lineups/{lineup_id}/check", response=api_response(LineupCheckOut))
def check_match_lineup(request: HttpRequest, lineup_id: int):
    """Возвращает ошибки и счётчики проверки состава капитана."""
    return check_captain_lineup(request_user_id(request), lineup_id)
