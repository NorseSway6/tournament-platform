from datetime import date as date_type

from django.http import HttpRequest
from django.utils import timezone as django_timezone
from ninja import Query, Router
from ninja.errors import HttpError

from apps.common.api_errors import api_response
from apps.identity_access.api.dependencies import access_token_auth, request_user_id
from apps.matches.access import judge_auth, require_judge_match, require_lease_takeover
from apps.matches.schemas.events import (
    MatchEventAppendOut,
    MatchEventCreate,
    MatchEventsBatchIn,
    MatchEventsBatchOut,
)
from apps.matches.schemas.lineups import JudgeLineupsOut
from apps.matches.schemas.public import (
    JudgeMatchesOut,
    MatchConfirmIn,
    MatchConfirmOut,
    MatchLeaseActionIn,
    MatchLeaseOut,
    MatchLeaseReleasedOut,
)
from apps.matches.selectors import matches_for_date, parse_timezone_name
from apps.matches.services.organizer import get_match_lineups_for_judge
from apps.matches.services.protocol import (
    acquire_match_lease,
    append_match_event,
    append_match_events,
    confirm_match,
    judge_match_ids,
    release_match_lease,
    renew_match_lease,
    takeover_match_lease,
)

judge_router = Router(tags=["Judge"], auth=judge_auth)


@judge_router.get("/matches/{match_id}/lineups", response=api_response(JudgeLineupsOut))
def judge_match_lineups(request: HttpRequest, match_id: int):
    """Возвращает заявки обоих участников матча и составы игроков."""
    require_judge_match(request, match_id)
    return get_match_lineups_for_judge(match_id)


@judge_router.get("/me/matches", response=api_response(JudgeMatchesOut))
def my_matches(
    request: HttpRequest,
    date: str = "today",
    timezone: str | None = Query(None, max_length=64),
):
    """Возвращает матчи судьи за дату, без пояса - поясам организаций."""
    try:
        tz = parse_timezone_name(timezone)
    except ValueError as error:
        raise HttpError(422, str(error)) from error
    if date == "today":
        match_date = None if timezone is None else django_timezone.localdate(timezone=tz)
    else:
        try:
            match_date = date_type.fromisoformat(date)
        except ValueError as error:
            raise HttpError(422, "date must be 'today' or an ISO date (YYYY-MM-DD)") from error
    matches = matches_for_date(
        match_date,
        judge_match_ids(request_user_id(request)),
        timezone_name=timezone,
    )
    return {
        "date": match_date or django_timezone.localdate(),
        "timezone": timezone,
        "items": matches,
        "total": len(matches),
    }


@judge_router.post("/matches/{match_id}/lease", response=api_response(MatchLeaseOut))
def lease_match(request: HttpRequest, match_id: int):
    """Захватывает матч для назначенного судьи на ограниченное время."""
    require_judge_match(request, match_id)
    return acquire_match_lease(match_id, request_user_id(request))


@judge_router.post("/matches/{match_id}/lease/renew", response=api_response(MatchLeaseOut))
def renew_lease(request: HttpRequest, match_id: int, payload: MatchLeaseActionIn):
    """Продлевает lease при наличии действующего lease-token."""
    require_judge_match(request, match_id)
    return renew_match_lease(match_id, request_user_id(request), payload.lease_token)


@judge_router.post(
    "/matches/{match_id}/lease/release", response=api_response(MatchLeaseReleasedOut)
)
def release_lease(request: HttpRequest, match_id: int, payload: MatchLeaseActionIn):
    """Освобождает lease и оставляет протокол и статус матча без изменений."""
    require_judge_match(request, match_id)
    return release_match_lease(match_id, request_user_id(request), payload.lease_token)


@judge_router.post(
    "/matches/{match_id}/lease/takeover",
    response=api_response(MatchLeaseOut),
    auth=access_token_auth,
)
def takeover_lease(request: HttpRequest, match_id: int):
    """Перехватывает live-матч только при отсутствующей или истёкшей аренде."""
    require_lease_takeover(request, match_id)
    return takeover_match_lease(match_id, request_user_id(request))


@judge_router.post(
    "/matches/{match_id}/events",
    response=api_response({201: MatchEventAppendOut, 200: MatchEventAppendOut}),
)
def post_match_event(request: HttpRequest, match_id: int, payload: MatchEventCreate):
    """Добавляет или идемпотентно повторяет событие и возвращает новый счёт."""
    require_judge_match(request, match_id)
    result, created = append_match_event(match_id, request_user_id(request), payload.model_dump())
    return (201 if created else 200, result)


@judge_router.post(
    "/matches/{match_id}/events/batch",
    response=api_response({201: MatchEventsBatchOut, 200: MatchEventsBatchOut}),
)
def post_match_events_batch(request: HttpRequest, match_id: int, payload: MatchEventsBatchIn):
    """Атомарно отправляет до 100 событий и возвращает итоговый счёт и seq."""
    require_judge_match(request, match_id)
    result, created = append_match_events(
        match_id,
        request_user_id(request),
        [event.model_dump() for event in payload.events],
        payload.lease_token,
    )
    return (201 if created else 200, result)


@judge_router.post("/matches/{match_id}/confirm", response=api_response(MatchConfirmOut))
def confirm_match_result(request: HttpRequest, match_id: int, payload: MatchConfirmIn):
    """Подтверждает завершённый матч после проверки lease-token"""
    require_judge_match(request, match_id)
    return confirm_match(match_id, request_user_id(request), payload.lease_token)
