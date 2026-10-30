from django.http import HttpRequest
from ninja import Query, Router

from apps.common.api_errors import api_response
from apps.tournaments.access import (
    require_organizer_group,
    require_organizer_organization_access,
    require_organizer_round,
    require_organizer_stage,
    require_organizer_tournament,
)
from apps.tournaments.access import tournament_organizer_auth as organizer_auth
from apps.tournaments.schemas.organizer import (
    GroupEntriesReplaceIn,
    GroupPatchIn,
    GroupWriteIn,
    OrganizerEntriesOut,
    OrganizerGroupEntriesOut,
    OrganizerGroupOut,
    OrganizerGroupsOut,
    OrganizerRoundOut,
    OrganizerRoundsOut,
    OrganizerStageOut,
    OrganizerStagesOut,
    OrganizerTournamentListOut,
    OrganizerTournamentOut,
    OrganizerTournamentPatchIn,
    OrganizerTournamentWriteIn,
    RegulationIn,
    RoundPatchIn,
    RoundWriteIn,
    StagePatchIn,
    StageWriteIn,
)
from apps.tournaments.services.structure import (
    create_organizer_group,
    create_organizer_round,
    create_organizer_stage,
    delete_organizer_group,
    delete_organizer_round,
    delete_organizer_stage,
    list_organizer_group_entries,
    list_organizer_groups,
    list_organizer_rounds,
    list_organizer_stages,
    replace_organizer_group_entries,
    update_organizer_group,
    update_organizer_round,
    update_organizer_stage,
)
from apps.tournaments.services.tournaments import (
    create_organizer_tournament,
    delete_organizer_tournament,
    finish_organizer_tournament,
    get_organizer_tournament,
    list_organizer_tournaments,
    open_tournament_registration,
    organizer_entries,
    replace_organizer_regulation,
    start_organizer_tournament,
    update_organizer_tournament,
)

require_organizer_organization = require_organizer_organization_access

organizer_router = Router(tags=["Organizer — tournaments"], auth=organizer_auth)


@organizer_router.get("/tournaments", response=api_response(OrganizerTournamentListOut))
def organizer_tournament_list(request: HttpRequest, organization_id: int = Query(..., ge=1)):
    """Возвращает турниры для указанной организации"""
    require_organizer_organization_access(request, organization_id)
    items = list_organizer_tournaments(organization_id, request.auth.pk)
    return {"items": items, "total": len(items)}


@organizer_router.post("/tournaments", response=api_response({201: OrganizerTournamentOut}))
def organizer_tournament_create(request: HttpRequest, payload: OrganizerTournamentWriteIn):
    """Создает турнир в рамках указанной организации"""
    require_organizer_organization(request, payload.organization_id)
    tournament = create_organizer_tournament(payload.model_dump())
    return 201, tournament


@organizer_router.get("/tournaments/{tournament_id}", response=api_response(OrganizerTournamentOut))
def organizer_tournament_detail(request: HttpRequest, tournament_id: int):
    """Возвращает один турнир"""
    require_organizer_tournament(request, tournament_id)
    return get_organizer_tournament(tournament_id)


@organizer_router.patch(
    "/tournaments/{tournament_id}",
    response=api_response(OrganizerTournamentOut),
)
def organizer_tournament_patch(
    request: HttpRequest, tournament_id: int, payload: OrganizerTournamentPatchIn
):
    """Частично обновляет редактируемые поля турнира."""
    require_organizer_tournament(request, tournament_id)
    return update_organizer_tournament(tournament_id, payload.model_dump(exclude_unset=True))


@organizer_router.delete("/tournaments/{tournament_id}", response=api_response({204: None}))
def organizer_tournament_delete(request: HttpRequest, tournament_id: int):
    """Удаляет турнир, если для него ещё нет заявок и матчей."""
    require_organizer_tournament(request, tournament_id)
    delete_organizer_tournament(tournament_id)
    return 204, None


@organizer_router.post(
    "/tournaments/{tournament_id}/open-registration",
    response=api_response(OrganizerTournamentOut),
)
def organizer_tournament_open_registration(request: HttpRequest, tournament_id: int):
    """Переводит черновик турнира в приём заявок."""
    require_organizer_tournament(request, tournament_id)
    return open_tournament_registration(tournament_id)


@organizer_router.post(
    "/tournaments/{tournament_id}/start",
    response=api_response(OrganizerTournamentOut),
)
def organizer_tournament_start(request: HttpRequest, tournament_id: int):
    """Начинает турнир и замораживает его регламент."""
    require_organizer_tournament(request, tournament_id)
    return start_organizer_tournament(tournament_id)


@organizer_router.post(
    "/tournaments/{tournament_id}/finish",
    response=api_response(OrganizerTournamentOut),
)
def organizer_tournament_finish(request: HttpRequest, tournament_id: int):
    """Завершает турнир, находящийся в стадии проведения."""
    require_organizer_tournament(request, tournament_id)
    return finish_organizer_tournament(tournament_id)


@organizer_router.put(
    "/tournaments/{tournament_id}/regulation",
    response=api_response(OrganizerTournamentOut),
)
def organizer_regulation_replace(request: HttpRequest, tournament_id: int, payload: RegulationIn):
    """Целиком заменяет регламент турнира до его старта."""
    require_organizer_tournament(request, tournament_id)
    return replace_organizer_regulation(tournament_id, payload.regulation)


@organizer_router.get(
    "/tournaments/{tournament_id}/entries", response=api_response(OrganizerEntriesOut)
)
def organizer_entries_list(request: HttpRequest, tournament_id: int):
    """Возвращает заявки команд в турнире организации-организатора."""
    require_organizer_tournament(request, tournament_id)
    items = organizer_entries(tournament_id)
    return {"items": items, "total": len(items)}


@organizer_router.get(
    "/tournaments/{tournament_id}/stages",
    response=api_response(OrganizerStagesOut),
)
def organizer_stages_list(request: HttpRequest, tournament_id: int):
    """Возвращает этапы турнира организатора."""
    require_organizer_tournament(request, tournament_id)
    items = list_organizer_stages(tournament_id)
    return {"items": items, "total": len(items)}


@organizer_router.post(
    "/tournaments/{tournament_id}/stages",
    response=api_response({201: OrganizerStageOut}),
)
def organizer_stage_create(request: HttpRequest, tournament_id: int, payload: StageWriteIn):
    """Создаёт этап турнира."""
    require_organizer_tournament(request, tournament_id)
    stage = create_organizer_stage(tournament_id, payload.model_dump())
    return 201, stage


@organizer_router.patch(
    "/stages/{stage_id}",
    response=api_response(OrganizerStageOut),
)
def organizer_stage_update(request: HttpRequest, stage_id: int, payload: StagePatchIn):
    """Изменяет имя, тип или порядок этапа."""
    require_organizer_stage(request, stage_id)
    return update_organizer_stage(stage_id, payload.model_dump(exclude_unset=True))


@organizer_router.delete(
    "/stages/{stage_id}",
    response=api_response({204: None}),
)
def organizer_stage_delete(request: HttpRequest, stage_id: int):
    """Удаляет этап, если на него не ссылаются матчи."""
    require_organizer_stage(request, stage_id)
    delete_organizer_stage(stage_id)
    return 204, None


@organizer_router.get(
    "/stages/{stage_id}/groups",
    response=api_response(OrganizerGroupsOut),
)
def organizer_groups_list(request: HttpRequest, stage_id: int):
    """Возвращает группы группового этапа."""
    require_organizer_stage(request, stage_id)
    items = list_organizer_groups(stage_id)
    return {"items": items, "total": len(items)}


@organizer_router.post(
    "/stages/{stage_id}/groups",
    response=api_response({201: OrganizerGroupOut}),
)
def organizer_group_create(request: HttpRequest, stage_id: int, payload: GroupWriteIn):
    """Создаёт группу внутри этапа типа groups."""
    require_organizer_stage(request, stage_id)
    group = create_organizer_group(stage_id, payload.model_dump())
    return 201, group


@organizer_router.patch(
    "/groups/{group_id}",
    response=api_response(OrganizerGroupOut),
)
def organizer_group_update(request: HttpRequest, group_id: int, payload: GroupPatchIn):
    """Изменяет название или порядок группы."""
    require_organizer_group(request, group_id)
    return update_organizer_group(group_id, payload.model_dump(exclude_unset=True))


@organizer_router.delete(
    "/groups/{group_id}",
    response=api_response({204: None}),
)
def organizer_group_delete(request: HttpRequest, group_id: int):
    """Удаляет группу, если на неё не ссылаются матчи."""
    require_organizer_group(request, group_id)
    delete_organizer_group(group_id)
    return 204, None


@organizer_router.get(
    "/groups/{group_id}/entries",
    response=api_response(OrganizerGroupEntriesOut),
)
def organizer_group_entries_list(request: HttpRequest, group_id: int):
    """Возвращает заявки, явно назначенные в группу."""
    require_organizer_group(request, group_id)
    items = list_organizer_group_entries(group_id)
    return {"items": items, "total": len(items)}


@organizer_router.put(
    "/groups/{group_id}/entries",
    response=api_response(OrganizerGroupEntriesOut),
)
def organizer_group_entries_replace(
    request: HttpRequest, group_id: int, payload: GroupEntriesReplaceIn
):
    """Полностью заменяет список заявок, назначенных в группу."""
    require_organizer_group(request, group_id)
    items = replace_organizer_group_entries(group_id, payload.entry_ids)
    return {"items": items, "total": len(items)}


@organizer_router.get(
    "/stages/{stage_id}/rounds",
    response=api_response(OrganizerRoundsOut),
)
def organizer_rounds_list(request: HttpRequest, stage_id: int):
    """Возвращает туры указанного этапа."""
    require_organizer_stage(request, stage_id)
    items = list_organizer_rounds(stage_id)
    return {"items": items, "total": len(items)}


@organizer_router.post(
    "/stages/{stage_id}/rounds",
    response=api_response({201: OrganizerRoundOut}),
)
def organizer_round_create(request: HttpRequest, stage_id: int, payload: RoundWriteIn):
    """Создаёт тур внутри этапа."""
    require_organizer_stage(request, stage_id)
    round_obj = create_organizer_round(stage_id, payload.model_dump())
    return 201, round_obj


@organizer_router.patch(
    "/rounds/{round_id}",
    response=api_response(OrganizerRoundOut),
)
def organizer_round_update(request: HttpRequest, round_id: int, payload: RoundPatchIn):
    """Изменяет имя или порядок тура."""
    require_organizer_round(request, round_id)
    return update_organizer_round(round_id, payload.model_dump(exclude_unset=True))


@organizer_router.delete(
    "/rounds/{round_id}",
    response=api_response({204: None}),
)
def organizer_round_delete(request: HttpRequest, round_id: int):
    """Удаляет тур, если на него не ссылаются матчи."""
    require_organizer_round(request, round_id)
    delete_organizer_round(round_id)
    return 204, None
