from django.http import HttpRequest
from ninja import Router
from ninja.errors import HttpError

from config.api_errors import api_response
from apps.teams.schemas import (
    CaptainEntryOut,
    CaptainTeamCreateIn,
    CaptainTeamOut,
    CaptainTeamPatchIn,
    CaptainTeamsOut,
    EntryCreateIn,
    EntryPlayersOut,
    EntryPlayersReadOut,
    EntryPlayersUpdateIn,
    EntryDecisionIn,
    EntryDecisionOut,
    PlayerOut,
    TeamOut,
)
from apps.teams.services import (
    CaptainActionError,
    OrganizerEntryError,
    create_captain_tournament_entry,
    create_captain_team,
    decide_organizer_entry,
    get_captain_entry_players,
    list_captain_teams,
    update_captain_entry_players,
    update_captain_team,
)
from apps.teams.selectors import public_player, public_team

router = Router(tags=["Teams and players"])
captain_router = Router(tags=["Captain"])
organizer_router = Router(tags=["Organizer — entries"])


def _raise_captain_error(error: CaptainActionError) -> None:
    """Преобразует ошибку операции капитана в HTTP-ответ."""
    raise HttpError(error.status_code, str(error))


def _raise_organizer_error(error: OrganizerEntryError) -> None:
    """Преобразует ошибку решения по заявке в HTTP-ответ."""
    raise HttpError(error.status_code, str(error))


@router.get("/teams/{team_id}", response=api_response(TeamOut))
def get_team(request: HttpRequest, team_id: int):
    """Отдаёт публичную карточку команды"""
    team = public_team(team_id)
    if team is None:
        raise HttpError(404, "Team not found")
    return team


@router.get("/players/{player_id}", response=api_response(PlayerOut))
def get_player(request: HttpRequest, player_id: int):
    """Отдаёт публичную карточку игрока"""
    player = public_player(player_id)
    if player is None:
        raise HttpError(404, "Player not found")
    return player


@captain_router.post(
    "/tournaments/{tournament_id}/entries",
    response=api_response({201: CaptainEntryOut}),
)
def create_tournament_entry(
    request: HttpRequest, tournament_id: int, payload: EntryCreateIn
):
    """Подаёт заявку принадлежащей временному капитану команды."""
    try:
        entry = create_captain_tournament_entry(tournament_id, payload.team_id)
    except CaptainActionError as error:
        _raise_captain_error(error)
    return 201, entry


@captain_router.post("/teams", response=api_response({201: CaptainTeamOut}))
def create_team(request: HttpRequest, payload: CaptainTeamCreateIn):
    """Создаёт команду для временного капитана."""
    try:
        team = create_captain_team(payload.model_dump())
    except CaptainActionError as error:
        _raise_captain_error(error)
    return 201, team


@captain_router.get("/me/teams", response=api_response(CaptainTeamsOut))
def my_teams(request: HttpRequest):
    """Возвращает команды временного капитана и их заявки на турниры."""
    teams = list_captain_teams()
    return {"items": teams, "total": len(teams)}


@captain_router.patch("/teams/{team_id}", response=api_response(CaptainTeamOut))
def patch_team(request: HttpRequest, team_id: int, payload: CaptainTeamPatchIn):
    """Обновляет название или город команды временного капитана."""
    try:
        return update_captain_team(
            team_id, payload.model_dump(exclude_unset=True)
        )
    except CaptainActionError as error:
        _raise_captain_error(error)


@captain_router.get(
    "/entries/{entry_id}/players", response=api_response(EntryPlayersReadOut)
)
def get_entry_players(request: HttpRequest, entry_id: int):
    """Возвращает ростер заявки капитана, включая удалённых игроков."""
    try:
        return get_captain_entry_players(entry_id)
    except CaptainActionError as error:
        _raise_captain_error(error)


@captain_router.put(
    "/entries/{entry_id}/players", response=api_response(EntryPlayersOut)
)
def put_entry_players(
    request: HttpRequest, entry_id: int, payload: EntryPlayersUpdateIn
):
    """Заменяет список игроков заявки капитана и их игровые номера."""
    try:
        return update_captain_entry_players(
            entry_id, [player.model_dump() for player in payload.players]
        )
    except CaptainActionError as error:
        _raise_captain_error(error)


@organizer_router.patch(
    "/entries/{entry_id}", response=api_response(EntryDecisionOut)
)
def organizer_entry_decision(
    request: HttpRequest, entry_id: int, payload: EntryDecisionIn
):
    """Принимает или отклоняет ожидающую заявку турнира."""
    try:
        return decide_organizer_entry(
            entry_id, payload.status, payload.decision_comment
        )
    except OrganizerEntryError as error:
        _raise_organizer_error(error)
