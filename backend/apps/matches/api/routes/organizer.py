from datetime import date as date_type

from django.http import HttpRequest
from ninja import Query, Router
from ninja.errors import HttpError

from apps.common.api_errors import api_response
from apps.common.pagination import paginate
from apps.identity_access.api.dependencies import request_user_id
from apps.matches.access import organizer_auth, require_organizer_match
from apps.matches.schemas.events import ProtocolCorrectionIn, ProtocolCorrectionOut
from apps.matches.schemas.lineups import MatchLineupDecisionIn, MatchLineupDecisionOut
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
from apps.matches.schemas.public import MatchDetailOut, MatchPage
from apps.matches.schemas.types import MatchStatus
from apps.matches.selectors import get_organizer_match, organizer_matches
from apps.matches.services.organizer import (
    cancel_organizer_match,
    close_organizer_live_match,
    correct_organizer_match_event,
    create_organizer_match,
    create_organizer_venue,
    decide_organizer_match_lineup,
    delete_organizer_venue,
    get_organizer_venue,
    list_available_judges,
    list_organizer_venues,
    open_organizer_match_lineups,
    postpone_organizer_match,
    replace_match_officials,
    reschedule_organizer_match,
    set_organizer_match_technical_result,
    update_organizer_venue,
)
from apps.organizations.access import require_organizer_organization
from apps.tournaments.access import require_organizer_tournament

organizer_router = Router(tags=["Organizer — matches"], auth=organizer_auth)


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


@organizer_router.get(
    "/tournaments/{tournament_id}/matches",
    response=api_response(MatchPage),
)
def organizer_match_list(
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
    """Возвращает все матчи турнира организатора, включая черновики."""
    require_organizer_tournament(request, tournament_id)
    if date_from and date_to and date_from > date_to:
        raise HttpError(422, "date_from must be earlier than or equal to date_to")
    queryset = organizer_matches(
        tournament_id,
        status=status,
        team_id=team,
        stage_id=stage_id,
        round_id=round_id,
        group_id=group_id,
        date_from=date_from,
        date_to=date_to,
    )
    return paginate(queryset, page, page_size)


@organizer_router.get("/matches/{match_id}", response=api_response(MatchDetailOut))
def organizer_match_detail(request: HttpRequest, match_id: int):
    """Возвращает протокол матча организатору независимо от видимости турнира."""
    require_organizer_match(request, match_id)
    match = get_organizer_match(match_id)
    if match is None:
        raise HttpError(404, "Match not found")
    return match


@organizer_router.post(
    "/matches/{match_id}/open-lineups",
    response=api_response(OrganizerMatchOut),
)
def organizer_match_open_lineups(request: HttpRequest, match_id: int):
    """Открывает подачу заявок на матч, переводя его в lineups_open."""
    require_organizer_match(request, match_id)
    return open_organizer_match_lineups(match_id)


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
    """Регистрирует исправление протокола с обязательным указанием причины для целей аудита."""
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
    """Выводит список площадок, относящихся к организации, выбранной в URL-адресе."""
    require_organizer_organization(request, organization_id)
    items = list_organizer_venues(organization_id)
    return {"items": items, "total": len(items)}


@organizer_router.post(
    "/organizations/{organization_id}/venues", response=api_response({201: VenueOut})
)
def organizer_venue_create(request: HttpRequest, organization_id: int, payload: VenueWriteIn):
    """Создает площадку в рамках выбранной организации."""
    require_organizer_organization(request, organization_id)
    venue = create_organizer_venue(organization_id, payload.model_dump())
    return 201, venue


@organizer_router.get(
    "/organizations/{organization_id}/venues/{venue_id}", response=api_response(VenueOut)
)
def organizer_venue_detail(request: HttpRequest, organization_id: int, venue_id: int):
    """Возвращает один объект в рамках выбранной организации."""
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
    """Удаляет площадку, связанные матчи остаются без площадки."""
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
