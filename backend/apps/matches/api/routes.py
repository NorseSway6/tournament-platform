from datetime import date as date_type

from django.http import HttpRequest
from django.utils import timezone as django_timezone
from ninja import Query, Router
from ninja.errors import HttpError

from apps.identity_access.api.dependencies import access_token_auth, request_user_id
from apps.matches.access import (
    judge_auth,
    organizer_auth,
    require_judge_match,
    require_lease_takeover,
    require_organizer_match,
)
from apps.matches.schemas.events import (
    MatchEventAppendOut,
    MatchEventCreate,
    MatchEventFeedOut,
    MatchEventsBatchIn,
    MatchEventsBatchOut,
    ProtocolCorrectionIn,
    ProtocolCorrectionOut,
)
from apps.matches.schemas.lineups import (
    JudgeLineupsOut,
    LineupCheckOut,
    LineupUpdateIn,
    MatchLineupDecisionIn,
    MatchLineupDecisionOut,
    MatchLineupOut,
)
from apps.matches.schemas.organizer import (
    AvailableJudgesOut,
    MatchCloseLiveIn,
    MatchOfficialsIn,
    MatchOfficialsOut,
    MatchSchedulePatchIn,
    MatchTechnicalResultIn,
    OrganizerMatchCreateIn,
    OrganizerMatchOut,
    VenueListOut,
    VenueOut,
    VenuePatchIn,
    VenueWriteIn,
)
from apps.matches.schemas.public import (
    JudgeMatchesOut,
    MatchConfirmIn,
    MatchConfirmOut,
    MatchDetailOut,
    MatchLeaseActionIn,
    MatchLeaseOut,
    MatchLeaseReleasedOut,
    MatchPage,
    TodayOut,
)
from apps.matches.schemas.types import MatchStatus
from apps.matches.selectors import (
    get_match_event_feed,
    get_public_match,
    matches_for_captain_date,
    matches_for_date,
    parse_timezone_name,
    public_matches,
    public_matches_for_local_date,
)
from apps.matches.services.lineups import (
    check_captain_lineup,
    get_captain_match_lineup,
    submit_captain_match_lineup,
    update_captain_match_lineup,
)
from apps.matches.services.organizer import (
    cancel_organizer_match,
    close_organizer_live_match,
    correct_organizer_match_event,
    create_organizer_match,
    create_organizer_venue,
    decide_organizer_match_lineup,
    delete_organizer_venue,
    get_match_lineups_for_judge,
    get_organizer_venue,
    list_available_judges,
    list_organizer_venues,
    postpone_organizer_match,
    replace_match_officials,
    reschedule_organizer_match,
    set_organizer_match_technical_result,
    update_organizer_venue,
)
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
from apps.organizations.access import require_organizer_organization
from apps.teams.access import captain_auth
from apps.tournaments.access import require_organizer_tournament
from apps.tournaments.selectors import get_public_tournament
from config.api_errors import api_response
from config.pagination import paginate

router = Router(tags=["Matches"])
tournament_matches_router = Router(tags=["Tournament matches"])
today_router = Router(tags=["Today"])
judge_router = Router(tags=["Judge"], auth=judge_auth)
captain_router = Router(tags=["Captain"], auth=captain_auth)
organizer_router = Router(tags=["Organizer — matches"], auth=organizer_auth)


@judge_router.get("/matches/{match_id}/lineups", response=api_response(JudgeLineupsOut))
def judge_match_lineups(request: HttpRequest, match_id: int):
    """Возвращает заявки обоих участников матча и составы игроков."""
    require_judge_match(request, match_id)
    return get_match_lineups_for_judge(match_id)


@tournament_matches_router.get("/{tournament_id}/matches", response=api_response(MatchPage))
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
    """Возвращает отфильтрованную страницу матчей публичного турнира"""

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


@router.get("/{match_id}", response=api_response(MatchDetailOut))
def get_match(request: HttpRequest, match_id: int):
    """Возвращает публичный матч с лентой событий"""
    match = get_public_match(match_id)
    if match is None:
        raise HttpError(404, "Match not found")
    return match


@today_router.get("/today", response=api_response(TodayOut))
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


@judge_router.get("/me/matches", response=api_response(JudgeMatchesOut))
def my_matches(
    request: HttpRequest,
    date: str = "today",
    timezone: str | None = Query(None, max_length=64),
):
    """Возвращает матчи судьи за дату; без пояса используется пояс организации."""
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


@router.get("/{match_id}/events", response=api_response(MatchEventFeedOut))
def list_match_events(
    request: HttpRequest,
    match_id: int,
    after_seq: int = Query(0, ge=0),
):
    """Возвращает ленту событий после переданного номера sequence"""
    result = get_match_event_feed(match_id, after_seq)
    if result is None:
        raise HttpError(404, "Match not found")
    return result


@judge_router.post("/matches/{match_id}/confirm", response=api_response(MatchConfirmOut))
def confirm_match_result(request: HttpRequest, match_id: int, payload: MatchConfirmIn):
    """Подтверждает завершённый матч после проверки lease-token"""
    require_judge_match(request, match_id)
    return confirm_match(match_id, request_user_id(request), payload.lease_token)


@captain_router.get("/me/today", response=api_response(TodayOut))
def captain_today_matches(request: HttpRequest, timezone: str | None = Query(None, max_length=64)):
    """Возвращает сегодняшние матчи команд капитана; без пояса — по поясам организаций."""
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
    """Сохраняет состав капитана как черновик."""
    return update_captain_match_lineup(
        request_user_id(request), match_id, payload.model_dump()["players"]
    )


@captain_router.post("/matches/{match_id}/lineup/submit", response=api_response(LineupCheckOut))
def submit_match_lineup(request: HttpRequest, match_id: int):
    """Проверяет и отправляет состав матча на рассмотрение."""
    return submit_captain_match_lineup(request_user_id(request), match_id)


@captain_router.get("/lineups/{lineup_id}/check", response=api_response(LineupCheckOut))
def check_match_lineup(request: HttpRequest, lineup_id: int):
    """Возвращает ошибки и счётчики проверки состава капитана."""
    return check_captain_lineup(request_user_id(request), lineup_id)


@organizer_router.post(
    "/tournaments/{tournament_id}/matches",
    response=api_response({201: OrganizerMatchOut}),
)
def organizer_match_create(
    request: HttpRequest, tournament_id: int, payload: OrganizerMatchCreateIn
):
    """Создаёт матч в этапе турнира организации-организатора."""
    require_organizer_tournament(request, tournament_id)
    match = create_organizer_match(tournament_id, payload.model_dump())
    return 201, match


@organizer_router.patch("/matches/{match_id}/schedule", response=api_response(OrganizerMatchOut))
def organizer_match_reschedule(request: HttpRequest, match_id: int, payload: MatchSchedulePatchIn):
    """Переносит запланированный или отложенный матч."""
    require_organizer_match(request, match_id)
    return reschedule_organizer_match(match_id, payload.model_dump(exclude_unset=True))


@organizer_router.post("/matches/{match_id}/cancel", response=api_response(OrganizerMatchOut))
def organizer_match_cancel(request: HttpRequest, match_id: int):
    """Отменяет матч, который ещё не был завершён."""
    require_organizer_match(request, match_id)
    return cancel_organizer_match(match_id)


@organizer_router.post("/matches/{match_id}/postpone", response=api_response(OrganizerMatchOut))
def organizer_match_postpone(request: HttpRequest, match_id: int):
    """Переводит запланированный матч в статус отложенного."""
    require_organizer_match(request, match_id)
    return postpone_organizer_match(match_id)


@organizer_router.post(
    "/matches/{match_id}/technical-result",
    response=api_response(OrganizerMatchOut),
)
def organizer_match_technical_result(
    request: HttpRequest, match_id: int, payload: MatchTechnicalResultIn
):
    """Присваивает матчу технический результат с итоговым счётом."""
    require_organizer_match(request, match_id)
    return set_organizer_match_technical_result(
        match_id,
        payload.home_score,
        payload.away_score,
        payload.result_type,
    )


@organizer_router.post(
    "/matches/{match_id}/close-live",
    response=api_response(OrganizerMatchOut),
)
def organizer_match_close_live(request: HttpRequest, match_id: int, payload: MatchCloseLiveIn):
    """Принудительно завершает зависший live-матч с указанным счётом."""
    require_organizer_match(request, match_id)
    return close_organizer_live_match(match_id, payload.home_score, payload.away_score)


@organizer_router.put("/matches/{match_id}/officials", response=api_response(MatchOfficialsOut))
def organizer_match_officials(request: HttpRequest, match_id: int, payload: MatchOfficialsIn):
    """Полностью назначает официальных лиц матча."""
    require_organizer_match(request, match_id)
    return replace_match_officials(match_id, [item.model_dump() for item in payload.officials])


@organizer_router.post(
    "/matches/{match_id}/corrections",
    response=api_response(ProtocolCorrectionOut),
)
def organizer_protocol_correction(
    request: HttpRequest,
    match_id: int,
    payload: ProtocolCorrectionIn,
):
    """Records an append-only correction with a mandatory audit reason."""
    require_organizer_match(request, match_id)
    return correct_organizer_match_event(
        match_id,
        request_user_id(request),
        payload.target_event_id,
        payload.action,
        payload.replacement.model_dump() if payload.replacement else None,
        payload.reason,
    )


@organizer_router.get(
    "/organizations/{organization_id}/venues", response=api_response(VenueListOut)
)
def organizer_venues_list(request: HttpRequest, organization_id: int):
    """Lists venues under the organization selected in the URL."""
    require_organizer_organization(request, organization_id)
    items = list_organizer_venues(organization_id)
    return {"items": items, "total": len(items)}


@organizer_router.post(
    "/organizations/{organization_id}/venues", response=api_response({201: VenueOut})
)
def organizer_venue_create(request: HttpRequest, organization_id: int, payload: VenueWriteIn):
    """Creates a venue under the selected organization."""
    require_organizer_organization(request, organization_id)
    venue = create_organizer_venue(organization_id, payload.model_dump())
    return 201, venue


@organizer_router.get(
    "/organizations/{organization_id}/venues/{venue_id}", response=api_response(VenueOut)
)
def organizer_venue_detail(request: HttpRequest, organization_id: int, venue_id: int):
    """Returns one venue within the selected organization."""
    require_organizer_organization(request, organization_id)
    return get_organizer_venue(organization_id, venue_id)


@organizer_router.patch(
    "/organizations/{organization_id}/venues/{venue_id}", response=api_response(VenueOut)
)
def organizer_venue_patch(
    request: HttpRequest, organization_id: int, venue_id: int, payload: VenuePatchIn
):
    """Частично обновляет данные площадки."""
    require_organizer_organization(request, organization_id)
    return update_organizer_venue(organization_id, venue_id, payload.model_dump(exclude_unset=True))


@organizer_router.delete(
    "/organizations/{organization_id}/venues/{venue_id}", response=api_response({204: None})
)
def organizer_venue_delete(request: HttpRequest, organization_id: int, venue_id: int):
    """Удаляет площадку; связанные матчи остаются без площадки."""
    require_organizer_organization(request, organization_id)
    delete_organizer_venue(organization_id, venue_id)
    return 204, None


@organizer_router.get(
    "/organizations/{organization_id}/judges", response=api_response(AvailableJudgesOut)
)
def organizer_available_judges(request: HttpRequest, organization_id: int):
    """Возвращает активных судей из пула выбранной организации."""
    require_organizer_organization(request, organization_id)
    items = list_available_judges(organization_id)
    return {"items": items, "total": len(items)}


@organizer_router.patch("/lineups/{lineup_id}", response=api_response(MatchLineupDecisionOut))
def organizer_match_lineup_decision(
    request: HttpRequest, lineup_id: int, payload: MatchLineupDecisionIn
):
    """Принимает или отклоняет отправленный капитаном состав на матч."""
    from apps.matches.models import MatchLineup

    match_id = MatchLineup.objects.filter(pk=lineup_id).values_list("match_id", flat=True).first()
    if match_id is None:
        raise HttpError(404, "Lineup not found")
    require_organizer_match(request, match_id)
    return decide_organizer_match_lineup(lineup_id, payload.status, payload.reject_reason)
