from datetime import date as Date
from django.http import HttpRequest
from django.utils import timezone
from ninja import Query, Router
from ninja.errors import HttpError

from config.api_errors import api_response
from config.pagination import paginate
from apps.matches.schemas import (
    JudgeMatchesOut,
    JudgeLineupsOut,
    MatchLineupDecisionIn,
    MatchLineupDecisionOut,
    LineupCheckOut,
    LineupUpdateIn,
    MatchConfirmIn,
    MatchConfirmOut,
    MatchDetailOut,
    MatchEventCreate,
    MatchEventAppendOut,
    MatchEventFeedOut,
    MatchEventOut,
    MatchEventsBatchIn,
    MatchEventsBatchOut,
    MatchLeaseOut,
    MatchLeaseActionIn,
    MatchLeaseReleasedOut,
    MatchLineupOut,
    MatchOut,
    MatchPage,
    MatchOfficialsIn,
    MatchOfficialsOut,
    MatchStatus,
    AvailableJudgesOut,
    VenueListOut,
    VenueOut,
    VenuePatchIn,
    VenueWriteIn,
    MatchSchedulePatchIn,
    OrganizerMatchCreateIn,
    OrganizerMatchOut,
    ProtocolCorrectionIn,
    ProtocolCorrectionOut,
    TodayOut,
)
from apps.matches.selectors import (
    get_match_event_feed,
    get_public_match,
    matches_for_captain_date,
    matches_for_date,
    public_matches,
)
from apps.matches.services.protocol import (
    MatchActionError,
    acquire_match_lease,
    append_match_event,
    append_match_events,
    confirm_match,
    release_match_lease,
    renew_match_lease,
    takeover_match_lease,
    temporary_judge_match_ids,
)
from apps.matches.services.lineups import (
    LineupActionError,
    TEMPORARY_CAPTAIN_ID,
    check_captain_lineup,
    get_captain_match_lineup,
    submit_captain_match_lineup,
    update_captain_match_lineup,
)
from apps.matches.services.organizer import (
    OrganizerMatchError,
    correct_organizer_match_event,
    create_organizer_venue,
    create_organizer_match,
    decide_organizer_match_lineup,
    delete_organizer_venue,
    get_match_lineups_for_judge,
    get_organizer_venue,
    list_available_judges,
    list_organizer_venues,
    replace_match_officials,
    reschedule_organizer_match,
    update_organizer_venue,
)
from apps.tournaments.selectors import get_public_tournament

router = Router(tags=["Matches"])
tournament_matches_router = Router(tags=["Tournament matches"])
today_router = Router(tags=["Today"])
judge_router = Router(tags=["Judge"])
captain_router = Router(tags=["Captain"])
organizer_router = Router(tags=["Organizer — matches"])
def _raise_api_error(error: MatchActionError) -> None:
    """Преобразует ошибку операции матча в HTTP-ответ"""
    raise HttpError(error.status_code, str(error))


def _raise_lineup_error(error: LineupActionError) -> None:
    """Преобразует ошибку операции с составом в HTTP-ответ."""
    raise HttpError(error.status_code, str(error))


def _raise_organizer_match_error(error: OrganizerMatchError) -> None:
    """Преобразует ошибку организатора по матчу в HTTP-ответ."""
    raise HttpError(error.status_code, str(error))


@judge_router.get(
    "/matches/{match_id}/lineups", response=api_response(JudgeLineupsOut)
)
def judge_match_lineups(request: HttpRequest, match_id: int):
    """Возвращает заявки обоих участников матча и составы игроков."""
    try:
        return get_match_lineups_for_judge(match_id)
    except OrganizerMatchError as error:
        _raise_organizer_match_error(error)


@tournament_matches_router.get(
    "/{tournament_id}/matches", response=api_response(MatchPage)
)
def list_tournament_matches(
    request: HttpRequest,
    tournament_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: MatchStatus | None = None,
    team: int | None = Query(None, ge=1),
    date_from: Date | None = None,
    date_to: Date | None = None,
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
def today_matches(request: HttpRequest):
    """Возвращает публичные матчи, назначенные на текущую локальную дату"""
    today = timezone.localdate()
    queryset = public_matches(date_from=today, date_to=today)
    matches = list(queryset)
    return {
        "date": today,
        "items": matches,
        "total": len(matches),
    }


@judge_router.get("/me/matches", response=api_response(JudgeMatchesOut))
def my_matches(request: HttpRequest, date: str = "today"):
    """Возвращает матчи временного judge-ID, занятые им через lease"""
    match_date = timezone.localdate() if date == "today" else None
    if match_date is None:
        try:
            match_date = Date.fromisoformat(date)
        except ValueError:
            raise HttpError(422, "date must be 'today' or an ISO date (YYYY-MM-DD)")
    matches = list(matches_for_date(match_date, temporary_judge_match_ids()))
    return {"date": match_date, "items": matches, "total": len(matches)}


@router.post("/{match_id}/lease", response=api_response(MatchLeaseOut))
def lease_match(request: HttpRequest, match_id: int):
    """Захватывает матч для временного судьи на ограниченное время"""
    try:
        return acquire_match_lease(match_id)
    except MatchActionError as error:
        _raise_api_error(error)


@router.post("/{match_id}/lease/renew", response=api_response(MatchLeaseOut))
def renew_lease(request: HttpRequest, match_id: int, payload: MatchLeaseActionIn):
    """Продлевает lease при наличии действующего lease-token."""
    try:
        return renew_match_lease(match_id, payload.lease_token)
    except MatchActionError as error:
        _raise_api_error(error)


@router.post("/{match_id}/lease/release", response=api_response(MatchLeaseReleasedOut))
def release_lease(request: HttpRequest, match_id: int, payload: MatchLeaseActionIn):
    """Освобождает lease и оставляет протокол и статус матча без изменений."""
    try:
        return release_match_lease(match_id, payload.lease_token)
    except MatchActionError as error:
        _raise_api_error(error)


@router.post("/{match_id}/lease/takeover", response=api_response(MatchLeaseOut))
def takeover_lease(request: HttpRequest, match_id: int):
    """Перехватывает live-матч, выдавая новый токен и отзывая предыдущий."""
    try:
        return takeover_match_lease(match_id)
    except MatchActionError as error:
        _raise_api_error(error)


@router.post(
    "/{match_id}/events",
    response=api_response({201: MatchEventAppendOut, 200: MatchEventAppendOut}),
)
def post_match_event(request: HttpRequest, match_id: int, payload: MatchEventCreate):
    """Добавляет или идемпотентно повторяет событие и возвращает новый счёт."""
    try:
        result, created = append_match_event(match_id, payload.model_dump())
    except MatchActionError as error:
        _raise_api_error(error)
    return (201 if created else 200, result)


@router.post(
    "/{match_id}/events/batch",
    response=api_response({201: MatchEventsBatchOut, 200: MatchEventsBatchOut}),
)
def post_match_events_batch(
    request: HttpRequest, match_id: int, payload: MatchEventsBatchIn
):
    """Атомарно отправляет до 100 событий и возвращает итоговый счёт и seq."""
    try:
        result, created = append_match_events(
            match_id,
            [event.model_dump() for event in payload.events],
            payload.lease_token,
        )
    except MatchActionError as error:
        _raise_api_error(error)
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


@router.post("/{match_id}/confirm", response=api_response(MatchConfirmOut))
def confirm_match_result(request: HttpRequest, match_id: int, payload: MatchConfirmIn):
    """Подтверждает завершённый матч после проверки lease-token"""
    try:
        return confirm_match(match_id, payload.lease_token)
    except MatchActionError as error:
        _raise_api_error(error)


@captain_router.get("/me/today", response=api_response(TodayOut))
def captain_today_matches(request: HttpRequest):
    """Возвращает матчи сегодняшнего дня команд временного капитана."""
    today = timezone.localdate()
    matches = list(matches_for_captain_date(today, TEMPORARY_CAPTAIN_ID))
    return {"date": today, "items": matches, "total": len(matches)}


@captain_router.get(
    "/matches/{match_id}/lineup", response=api_response(MatchLineupOut)
)
def get_captain_lineup(request: HttpRequest, match_id: int):
    """Возвращает текущий состав или предзаполненный ростер капитана."""
    try:
        return get_captain_match_lineup(match_id)
    except LineupActionError as error:
        _raise_lineup_error(error)


@captain_router.put(
    "/matches/{match_id}/lineup", response=api_response(MatchLineupOut)
)
def put_captain_lineup(
    request: HttpRequest, match_id: int, payload: LineupUpdateIn
):
    """Сохраняет состав капитана как черновик."""
    try:
        return update_captain_match_lineup(match_id, payload.model_dump()["players"])
    except LineupActionError as error:
        _raise_lineup_error(error)


@captain_router.post(
    "/matches/{match_id}/lineup/submit", response=api_response(LineupCheckOut)
)
def submit_match_lineup(request: HttpRequest, match_id: int):
    """Проверяет и отправляет состав матча на рассмотрение."""
    try:
        return submit_captain_match_lineup(match_id)
    except LineupActionError as error:
        _raise_lineup_error(error)


@captain_router.get(
    "/lineups/{lineup_id}/check", response=api_response(LineupCheckOut)
)
def check_match_lineup(request: HttpRequest, lineup_id: int):
    """Возвращает ошибки и счётчики проверки состава капитана."""
    try:
        return check_captain_lineup(lineup_id)
    except LineupActionError as error:
        _raise_lineup_error(error)


@organizer_router.post(
    "/tournaments/{tournament_id}/matches",
    response=api_response({201: OrganizerMatchOut}),
)
def organizer_match_create(
    request: HttpRequest, tournament_id: int, payload: OrganizerMatchCreateIn
):
    """Создаёт матч в этапе турнира организации-организатора."""
    try:
        match = create_organizer_match(tournament_id, payload.model_dump())
    except OrganizerMatchError as error:
        _raise_organizer_match_error(error)
    return 201, match


@organizer_router.patch(
    "/matches/{match_id}/schedule", response=api_response(OrganizerMatchOut)
)
def organizer_match_reschedule(
    request: HttpRequest, match_id: int, payload: MatchSchedulePatchIn
):
    """Переносит запланированный или отложенный матч."""
    try:
        return reschedule_organizer_match(
            match_id, payload.model_dump(exclude_unset=True)
        )
    except OrganizerMatchError as error:
        _raise_organizer_match_error(error)


@organizer_router.put(
    "/matches/{match_id}/officials", response=api_response(MatchOfficialsOut)
)
def organizer_match_officials(
    request: HttpRequest, match_id: int, payload: MatchOfficialsIn
):
    """Полностью назначает официальных лиц матча."""
    try:
        return replace_match_officials(
            match_id, [item.model_dump() for item in payload.officials]
        )
    except OrganizerMatchError as error:
        _raise_organizer_match_error(error)


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
    try:
        return correct_organizer_match_event(
            match_id,
            payload.target_event_id,
            payload.action,
            payload.replacement.model_dump() if payload.replacement else None,
            payload.reason,
        )
    except OrganizerMatchError as error:
        _raise_organizer_match_error(error)


@organizer_router.get("/organizations/{organization_id}/venues", response=api_response(VenueListOut))
def organizer_venues_list(request: HttpRequest, organization_id: int):
    """Lists venues under the organization selected in the URL."""
    try:
        items = list_organizer_venues(organization_id)
    except OrganizerMatchError as error:
        _raise_organizer_match_error(error)
    return {"items": items, "total": len(items)}


@organizer_router.post("/organizations/{organization_id}/venues", response=api_response({201: VenueOut}))
def organizer_venue_create(request: HttpRequest, organization_id: int, payload: VenueWriteIn):
    """Creates a venue under the selected organization."""
    try:
        venue = create_organizer_venue(organization_id, payload.model_dump())
    except OrganizerMatchError as error:
        _raise_organizer_match_error(error)
    return 201, venue


@organizer_router.get("/organizations/{organization_id}/venues/{venue_id}", response=api_response(VenueOut))
def organizer_venue_detail(request: HttpRequest, organization_id: int, venue_id: int):
    """Returns one venue within the selected organization."""
    try:
        return get_organizer_venue(organization_id, venue_id)
    except OrganizerMatchError as error:
        _raise_organizer_match_error(error)


@organizer_router.patch("/organizations/{organization_id}/venues/{venue_id}", response=api_response(VenueOut))
def organizer_venue_patch(request: HttpRequest, organization_id: int, venue_id: int, payload: VenuePatchIn):
    """Частично обновляет данные площадки."""
    try:
        return update_organizer_venue(organization_id, venue_id, payload.model_dump(exclude_unset=True))
    except OrganizerMatchError as error:
        _raise_organizer_match_error(error)


@organizer_router.delete("/organizations/{organization_id}/venues/{venue_id}", response=api_response({204: None}))
def organizer_venue_delete(request: HttpRequest, organization_id: int, venue_id: int):
    """Удаляет площадку; связанные матчи остаются без площадки."""
    try:
        delete_organizer_venue(organization_id, venue_id)
    except OrganizerMatchError as error:
        _raise_organizer_match_error(error)
    return 204, None


@organizer_router.get("/organizations/{organization_id}/judges", response=api_response(AvailableJudgesOut))
def organizer_available_judges(request: HttpRequest, organization_id: int):
    """Возвращает активные учётные записи для назначения официальными лицами."""
    try:
        items = list_available_judges(organization_id)
    except OrganizerMatchError as error:
        _raise_organizer_match_error(error)
    return {"items": items, "total": len(items)}


@organizer_router.patch(
    "/lineups/{lineup_id}", response=api_response(MatchLineupDecisionOut)
)
def organizer_match_lineup_decision(
    request: HttpRequest, lineup_id: int, payload: MatchLineupDecisionIn
):
    """Принимает или отклоняет отправленный капитаном состав на матч."""
    try:
        return decide_organizer_match_lineup(
            lineup_id, payload.status, payload.reject_reason
        )
    except OrganizerMatchError as error:
        _raise_organizer_match_error(error)
