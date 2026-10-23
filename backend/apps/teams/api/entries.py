from django.http import HttpRequest
from ninja import Router
from ninja.errors import HttpError

from config.api_errors import api_response
from apps.identity_access.api.dependencies import request_user_id
from apps.teams.access import captain_auth
from apps.teams.schemas.captain import CaptainEntryOut, EntryCreateIn
from apps.teams.services.entries import create_captain_tournament_entry
from apps.tournaments.schemas.public import PublicParticipantsOut
from apps.tournaments.selectors import get_public_tournament

router = Router(tags=["Tournament entries"])


@router.get("/tournaments/{tournament_id}/entries", response=api_response(PublicParticipantsOut))
def tournament_participants(request: HttpRequest, tournament_id: int):
    """Возвращает принятые команды турнира, доступного для публичного просмотра."""
    tournament = get_public_tournament(tournament_id)
    if tournament is None:
        raise HttpError(404, "Tournament not found")
    entries = list(
        tournament.entries.filter(status="accepted")
        .select_related("team")
        .order_by("team__name", "team_id", "id")
    )
    return {"items": [entry.team for entry in entries], "total": len(entries)}


@router.post(
    "/tournaments/{tournament_id}/entries",
    response=api_response({201: CaptainEntryOut}),
    tags=["Captain"],
    auth=captain_auth,
)
def create_tournament_entry(
    request: HttpRequest, tournament_id: int, payload: EntryCreateIn
):
    """Подаёт заявку принадлежащей текущему капитану команды."""
    entry = create_captain_tournament_entry(
        request_user_id(request), tournament_id, payload.team_id
    )
    return 201, entry
