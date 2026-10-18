from typing import Literal

from django.http import HttpRequest
from ninja import Query, Router
from ninja.errors import HttpError

from config.pagination import paginate
from apps.standings_stats.services import calculate_tournament_standings
from apps.tournaments.schemas import StandingsOut, TournamentListResponse, TournamentOut
from apps.tournaments.selectors import (
    get_public_tournament,
    public_tournaments,
)

router = Router(tags=["Tournaments"])
PublicTournamentStatus = Literal["registration", "ongoing", "finished"]
StageKind = Literal["league", "groups", "playoff"]


@router.get("", response=TournamentListResponse)
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


@router.get("/{tournament_id}", response=TournamentOut)
def get_tournament(request: HttpRequest, tournament_id: int):
    """Возвращает публичную карточку турнира"""
    tournament = get_public_tournament(tournament_id)
    if tournament is None:
        raise HttpError(404, "Tournament not found")
    return tournament


@router.get("/{tournament_id}/standings", response=StandingsOut)
def tournament_standings(request: HttpRequest, tournament_id: int):
    """Возвращает рассчитанные таблицы этапов публичного турнира"""
    tournament = get_public_tournament(tournament_id)
    if tournament is None:
        raise HttpError(404, "Tournament not found")
    return calculate_tournament_standings(tournament)
