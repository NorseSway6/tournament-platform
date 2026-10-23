from django.http import HttpRequest
from ninja import Router
from ninja.errors import HttpError

from config.api_errors import api_response
from apps.identity_access.api.dependencies import access_token_auth, request_user_id
from apps.teams.access import captain_auth
from apps.tournaments.access import tournament_organizer_auth as organizer_auth
from apps.teams.schemas.captain import (
    CaptainTeamCreateIn,
    CaptainTeamOut,
    CaptainTeamPatchIn,
    CaptainTeamsOut,
    EntryPlayersOut,
    EntryPlayersReadOut,
    EntryPlayersUpdateIn,
)
from apps.teams.schemas.common import PlayerOut, TeamOut
from apps.teams.schemas.organizer import (
    EntryDecisionIn,
    EntryDecisionOut,
)
from apps.teams.services.captain import (
    create_captain_team,
    list_captain_teams,
    update_captain_team,
)
from apps.teams.services.entries import (
    get_captain_entry_players,
    update_captain_entry_players,
)
from apps.teams.services.organizer import decide_organizer_entry
from apps.teams.selectors import public_player, public_team

router = Router(tags=["Teams and players"])
captain_router = Router(tags=["Captain"], auth=captain_auth)
organizer_router = Router(tags=["Organizer — entries"], auth=organizer_auth)






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


@captain_router.post("/teams", response=api_response({201: CaptainTeamOut}), auth=access_token_auth)
def create_team(request: HttpRequest, payload: CaptainTeamCreateIn):
    """Создаёт команду, привязанную к текущему пользователю как к капитану."""
    captain_id = request_user_id(request)
    team = create_captain_team(captain_id, payload.model_dump())
    return 201, team


@captain_router.get("/me/teams", response=api_response(CaptainTeamsOut))
def my_teams(request: HttpRequest):
    """Возвращает команды текущего капитана и их заявки на турниры."""
    teams = list_captain_teams(request_user_id(request))
    return {"items": teams, "total": len(teams)}


@captain_router.patch("/teams/{team_id}", response=api_response(CaptainTeamOut))
def patch_team(request: HttpRequest, team_id: int, payload: CaptainTeamPatchIn):
    """Обновляет название или город команды текущего капитана."""
    return update_captain_team(
        request_user_id(request), team_id, payload.model_dump(exclude_unset=True)
    )


@captain_router.get(
    "/entries/{entry_id}/players", response=api_response(EntryPlayersReadOut)
)
def get_entry_players(request: HttpRequest, entry_id: int):
    """Возвращает ростер заявки капитана, включая удалённых игроков."""
    return get_captain_entry_players(request_user_id(request), entry_id)


@captain_router.put(
    "/entries/{entry_id}/players", response=api_response(EntryPlayersOut)
)
def put_entry_players(
    request: HttpRequest, entry_id: int, payload: EntryPlayersUpdateIn
):
    """Заменяет список игроков заявки капитана и их игровые номера."""
    return update_captain_entry_players(
        request_user_id(request),
        entry_id,
        [player.model_dump() for player in payload.players],
    )


@organizer_router.patch(
    "/entries/{entry_id}", response=api_response(EntryDecisionOut)
)
def organizer_entry_decision(
    request: HttpRequest, entry_id: int, payload: EntryDecisionIn
):
    """Принимает или отклоняет ожидающую заявку турнира."""
    from apps.tournaments.access import require_organizer_tournament
    from apps.teams.models import TournamentEntry

    tournament_id = TournamentEntry.objects.filter(pk=entry_id).values_list(
        "tournament_id", flat=True
    ).first()
    if tournament_id is None:
        raise HttpError(404, "Entry not found")
    require_organizer_tournament(request, tournament_id)
    return decide_organizer_entry(
        entry_id, payload.status, payload.decision_comment
    )
