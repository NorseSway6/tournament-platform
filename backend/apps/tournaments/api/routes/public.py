from typing import Literal

from django.http import HttpRequest
from ninja import Query, Router
from ninja.errors import HttpError

from apps.common.api_errors import api_response
from apps.common.pagination import paginate
from apps.standings_stats.services import calculate_tournament_standings
from apps.tournaments.schemas.public import TournamentListResponse, TournamentOut
from apps.tournaments.schemas.scorers import ScorersOut
from apps.tournaments.schemas.standings import StandingsOut
from apps.tournaments.schemas.types import StageKind
from apps.tournaments.selectors import get_public_tournament, public_tournaments, tournament_scorers

public_router = Router(tags=["Tournaments"])
PublicTournamentStatus = Literal["registration", "ongoing", "finished"]


@public_router.get("", response=api_response(TournamentListResponse))
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


@public_router.get("/{tournament_id}", response=api_response(TournamentOut))
def get_tournament(request: HttpRequest, tournament_id: int):
    """Возвращает публичную карточку турнира"""
    tournament = get_public_tournament(tournament_id)
    if tournament is None:
        raise HttpError(404, "Tournament not found")
    return tournament


@public_router.get("/{tournament_id}/standings", response=api_response(StandingsOut))
def tournament_standings(request: HttpRequest, tournament_id: int):
    """Возвращает рассчитанные таблицы этапов публичного турнира"""
    tournament = get_public_tournament(tournament_id)
    if tournament is None:
        raise HttpError(404, "Tournament not found")
    return calculate_tournament_standings(tournament)


@public_router.get("/{tournament_id}/scorers", response=api_response(ScorersOut))
def tournament_scorers_list(request: HttpRequest, tournament_id: int):
    """Возвращает бомбардиров публичного турнира по голам."""
    tournament = get_public_tournament(tournament_id)
    if tournament is None:
        raise HttpError(404, "Tournament not found")
    items = tournament_scorers(tournament.id)
    return {"tournament_id": tournament.id, "items": items, "total": len(items)}
