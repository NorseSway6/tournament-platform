from datetime import date
from typing import Literal

from django.http import HttpRequest
from django.utils import timezone
from ninja import Query, Router
from ninja.errors import HttpError

from config.pagination import paginate
from apps.matches.schemas import MatchDetailOut, MatchOut, MatchPage, TodayOut
from apps.matches.selectors import get_public_match, public_matches
from apps.tournaments.selectors import get_public_tournament

router = Router(tags=["Matches"])
tournament_matches_router = Router(tags=["Tournament matches"])
today_router = Router(tags=["Today"])
MatchStatus = Literal[
    "scheduled",
    "lineups_open",
    "live",
    "finished",
    "confirmed",
    "postponed",
    "cancelled",
    "technical",
]


@tournament_matches_router.get("/{tournament_id}/matches", response=MatchPage)
def list_tournament_matches(
    request: HttpRequest,
    tournament_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: MatchStatus | None = None,
    team: int | None = Query(None, ge=1),
    date_from: date | None = None,
    date_to: date | None = None,
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
        date_from=date_from,
        date_to=date_to,
    )
    result = paginate(queryset, page, page_size)
    return result


@router.get("/{match_id}", response=MatchDetailOut)
def get_match(request: HttpRequest, match_id: int):
    """Возвращает публичный матч с лентой событий"""
    match = get_public_match(match_id)
    if match is None:
        raise HttpError(404, "Match not found")
    return match


@today_router.get("/today", response=TodayOut)
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
