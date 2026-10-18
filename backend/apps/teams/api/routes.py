from django.http import HttpRequest
from ninja import Router
from ninja.errors import HttpError

from apps.teams.schemas import PlayerOut, TeamOut
from apps.teams.selectors import public_player, public_team

router = Router(tags=["Teams and players"])


@router.get("/teams/{team_id}", response=TeamOut)
def get_team(request: HttpRequest, team_id: int):
    """Отдаёт публичную карточку команды"""
    team = public_team(team_id)
    if team is None:
        raise HttpError(404, "Team not found")
    return team


@router.get("/players/{player_id}", response=PlayerOut)
def get_player(request: HttpRequest, player_id: int):
    """Отдаёт публичную карточку игрока"""
    player = public_player(player_id)
    if player is None:
        raise HttpError(404, "Player not found")
    return player
