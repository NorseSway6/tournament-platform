from typing import Literal

from django.http import HttpRequest
from ninja import Query, Router
from ninja.errors import HttpError

from config.api_errors import api_response
from config.pagination import paginate
from apps.standings_stats.services import calculate_tournament_standings
from apps.tournaments.schemas import (
    StageKind,
    StandingsOut,
    TournamentListResponse,
    TournamentOut,
)
from apps.tournaments.schemas import (
    GroupPatchIn,
    GroupWriteIn,
    OrganizerEntriesOut,
    OrganizerGroupsOut,
    OrganizerRoundsOut,
    OrganizerStagesOut,
    PublicParticipantsOut,
    OrganizerGroupOut,
    OrganizerRoundOut,
    OrganizerStageOut,
    OrganizerTournamentListOut,
    OrganizerTournamentOut,
    OrganizerTournamentPatchIn,
    OrganizerTournamentWriteIn,
    RoundPatchIn,
    RoundWriteIn,
    RegulationIn,
    StagePatchIn,
    StageWriteIn,
)
from apps.tournaments.services import (
    OrganizerTournamentError,
    create_organizer_tournament,
    create_organizer_group,
    create_organizer_round,
    create_organizer_stage,
    delete_organizer_tournament,
    get_organizer_tournament,
    delete_organizer_group,
    delete_organizer_round,
    delete_organizer_stage,
    list_organizer_groups,
    list_organizer_rounds,
    list_organizer_stages,
    organizer_entries,
    list_organizer_tournaments,
    replace_organizer_regulation,
    update_organizer_tournament,
    update_organizer_group,
    update_organizer_round,
    update_organizer_stage,
)
from apps.tournaments.selectors import (
    get_public_tournament,
    public_tournaments,
)

router = Router(tags=["Tournaments"])
organizer_router = Router(tags=["Organizer — tournaments"])
PublicTournamentStatus = Literal["registration", "ongoing", "finished"]


@router.get("", response=api_response(TournamentListResponse))
def list_tournaments(
    request: HttpRequest,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: PublicTournamentStatus | None = None,
    league: StageKind | None = None,
):
    """Возвращает страницу публичных турниров с фильтрами"""
    queryset = public_tournaments(status=status, stage_kind=league)
    return paginate(queryset, page, page_size)


@router.get("/{tournament_id}", response=api_response(TournamentOut))
def get_tournament(request: HttpRequest, tournament_id: int):
    """Возвращает публичную карточку турнира"""
    tournament = get_public_tournament(tournament_id)
    if tournament is None:
        raise HttpError(404, "Tournament not found")
    return tournament


@router.get("/{tournament_id}/standings", response=api_response(StandingsOut))
def tournament_standings(request: HttpRequest, tournament_id: int):
    """Возвращает рассчитанные таблицы этапов публичного турнира"""
    tournament = get_public_tournament(tournament_id)
    if tournament is None:
        raise HttpError(404, "Tournament not found")
    return calculate_tournament_standings(tournament)


@router.get("/{tournament_id}/entries", response=api_response(PublicParticipantsOut))
def tournament_participants(request: HttpRequest, tournament_id: int):
    """Lists accepted teams only for a publicly visible tournament."""
    tournament = get_public_tournament(tournament_id)
    if tournament is None:
        raise HttpError(404, "Tournament not found")
    items = list(
        tournament.entries.filter(status="accepted")
        .select_related("team")
        .order_by("team__name", "team_id", "id")
    )
    return {"items": [item.team for item in items], "total": len(items)}


def _raise_organizer_error(error: OrganizerTournamentError) -> None:
    """Преобразует ошибку операции организатора в HTTP-ответ."""
    raise HttpError(error.status_code, str(error))


@organizer_router.get(
    "/tournaments", response=api_response(OrganizerTournamentListOut)
)
def organizer_tournament_list(request: HttpRequest, organization_id: int = Query(..., ge=1)):
    """Returns tournaments for an explicitly selected organization."""
    try:
        items = list_organizer_tournaments(organization_id)
    except OrganizerTournamentError as error:
        _raise_organizer_error(error)
    return {"items": items, "total": len(items)}


@organizer_router.post(
    "/tournaments", response=api_response({201: OrganizerTournamentOut})
)
def organizer_tournament_create(
    request: HttpRequest, payload: OrganizerTournamentWriteIn
):
    """Creates a tournament under the organization in the request body."""
    try:
        tournament = create_organizer_tournament(payload.model_dump())
    except OrganizerTournamentError as error:
        _raise_organizer_error(error)
    return 201, tournament


@organizer_router.get(
    "/tournaments/{tournament_id}", response=api_response(OrganizerTournamentOut)
)
def organizer_tournament_detail(request: HttpRequest, tournament_id: int):
    """Returns one tournament including its unpublished details."""
    try:
        return get_organizer_tournament(tournament_id)
    except OrganizerTournamentError as error:
        _raise_organizer_error(error)


@organizer_router.patch(
    "/tournaments/{tournament_id}",
    response=api_response(OrganizerTournamentOut),
)
def organizer_tournament_patch(
    request: HttpRequest, tournament_id: int, payload: OrganizerTournamentPatchIn
):
    """Частично обновляет редактируемые поля турнира."""
    try:
        return update_organizer_tournament(
            tournament_id, payload.model_dump(exclude_unset=True)
        )
    except OrganizerTournamentError as error:
        _raise_organizer_error(error)


@organizer_router.delete(
    "/tournaments/{tournament_id}", response=api_response({204: None})
)
def organizer_tournament_delete(request: HttpRequest, tournament_id: int):
    """Удаляет турнир, если для него ещё нет заявок и матчей."""
    try:
        delete_organizer_tournament(tournament_id)
    except OrganizerTournamentError as error:
        _raise_organizer_error(error)
    return 204, None


@organizer_router.put(
    "/tournaments/{tournament_id}/regulation",
    response=api_response(OrganizerTournamentOut),
)
def organizer_regulation_replace(
    request: HttpRequest, tournament_id: int, payload: RegulationIn
):
    """Целиком заменяет регламент турнира и проверяет правила таблицы."""
    try:
        return replace_organizer_regulation(tournament_id, payload.regulation)
    except OrganizerTournamentError as error:
        _raise_organizer_error(error)


@organizer_router.get(
    "/tournaments/{tournament_id}/entries", response=api_response(OrganizerEntriesOut)
)
def organizer_entries_list(request: HttpRequest, tournament_id: int):
    """Возвращает заявки команд в турнире организации-организатора."""
    try:
        items = organizer_entries(tournament_id)
    except OrganizerTournamentError as error:
        _raise_organizer_error(error)
    return {"items": items, "total": len(items)}


@organizer_router.get(
    "/tournaments/{tournament_id}/stages",
    response=api_response(OrganizerStagesOut),
)
def organizer_stages_list(request: HttpRequest, tournament_id: int):
    """Возвращает этапы турнира организатора."""
    try:
        items = list_organizer_stages(tournament_id)
    except OrganizerTournamentError as error:
        _raise_organizer_error(error)
    return {"items": items, "total": len(items)}


@organizer_router.post(
    "/tournaments/{tournament_id}/stages",
    response=api_response({201: OrganizerStageOut}),
)
def organizer_stage_create(request: HttpRequest, tournament_id: int, payload: StageWriteIn):
    """Создаёт этап турнира."""
    try:
        stage = create_organizer_stage(tournament_id, payload.model_dump())
    except OrganizerTournamentError as error:
        _raise_organizer_error(error)
    return 201, stage


@organizer_router.patch(
    "/stages/{stage_id}",
    response=api_response(OrganizerStageOut),
)
def organizer_stage_update(request: HttpRequest, stage_id: int, payload: StagePatchIn):
    """Изменяет имя, тип или порядок этапа."""
    try:
        return update_organizer_stage(stage_id, payload.model_dump(exclude_unset=True))
    except OrganizerTournamentError as error:
        _raise_organizer_error(error)


@organizer_router.delete(
    "/stages/{stage_id}",
    response=api_response({204: None}),
)
def organizer_stage_delete(request: HttpRequest, stage_id: int):
    """Удаляет этап, если на него не ссылаются матчи."""
    try:
        delete_organizer_stage(stage_id)
    except OrganizerTournamentError as error:
        _raise_organizer_error(error)
    return 204, None


@organizer_router.get(
    "/stages/{stage_id}/groups",
    response=api_response(OrganizerGroupsOut),
)
def organizer_groups_list(request: HttpRequest, stage_id: int):
    """Возвращает группы группового этапа."""
    try:
        items = list_organizer_groups(stage_id)
    except OrganizerTournamentError as error:
        _raise_organizer_error(error)
    return {"items": items, "total": len(items)}


@organizer_router.post(
    "/stages/{stage_id}/groups",
    response=api_response({201: OrganizerGroupOut}),
)
def organizer_group_create(request: HttpRequest, stage_id: int, payload: GroupWriteIn):
    """Создаёт группу внутри этапа типа groups."""
    try:
        group = create_organizer_group(stage_id, payload.model_dump())
    except OrganizerTournamentError as error:
        _raise_organizer_error(error)
    return 201, group


@organizer_router.patch(
    "/groups/{group_id}",
    response=api_response(OrganizerGroupOut),
)
def organizer_group_update(request: HttpRequest, group_id: int, payload: GroupPatchIn):
    """Изменяет название или порядок группы."""
    try:
        return update_organizer_group(group_id, payload.model_dump(exclude_unset=True))
    except OrganizerTournamentError as error:
        _raise_organizer_error(error)


@organizer_router.delete(
    "/groups/{group_id}",
    response=api_response({204: None}),
)
def organizer_group_delete(request: HttpRequest, group_id: int):
    """Удаляет группу, если на неё не ссылаются матчи."""
    try:
        delete_organizer_group(group_id)
    except OrganizerTournamentError as error:
        _raise_organizer_error(error)
    return 204, None


@organizer_router.get(
    "/stages/{stage_id}/rounds",
    response=api_response(OrganizerRoundsOut),
)
def organizer_rounds_list(request: HttpRequest, stage_id: int):
    """Возвращает туры указанного этапа."""
    try:
        items = list_organizer_rounds(stage_id)
    except OrganizerTournamentError as error:
        _raise_organizer_error(error)
    return {"items": items, "total": len(items)}


@organizer_router.post(
    "/stages/{stage_id}/rounds",
    response=api_response({201: OrganizerRoundOut}),
)
def organizer_round_create(request: HttpRequest, stage_id: int, payload: RoundWriteIn):
    """Создаёт тур внутри этапа."""
    try:
        round_obj = create_organizer_round(stage_id, payload.model_dump())
    except OrganizerTournamentError as error:
        _raise_organizer_error(error)
    return 201, round_obj


@organizer_router.patch(
    "/rounds/{round_id}",
    response=api_response(OrganizerRoundOut),
)
def organizer_round_update(request: HttpRequest, round_id: int, payload: RoundPatchIn):
    """Изменяет имя или порядок тура."""
    try:
        return update_organizer_round(round_id, payload.model_dump(exclude_unset=True))
    except OrganizerTournamentError as error:
        _raise_organizer_error(error)


@organizer_router.delete(
    "/rounds/{round_id}",
    response=api_response({204: None}),
)
def organizer_round_delete(request: HttpRequest, round_id: int):
    """Удаляет тур, если на него не ссылаются матчи."""
    try:
        delete_organizer_round(round_id)
    except OrganizerTournamentError as error:
        _raise_organizer_error(error)
    return 204, None
