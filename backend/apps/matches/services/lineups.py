from django.db import transaction

from config.temporary_ids import TEMPORARY_CAPTAIN_ID
from apps.matches.models import Match, MatchLineup, MatchLineupPlayer
from apps.teams.models import EntryPlayer, TournamentEntry


class LineupActionError(Exception):
    """Сообщает об ошибке операции капитана с составом на матч."""

    def __init__(self, message: str, status_code: int = 409):
        super().__init__(message)
        self.status_code = status_code


def captain_entry_for_match(match_id: int) -> tuple[Match, TournamentEntry]:
    """Находит заявку команды временного капитана среди участников матча."""
    match = (
        Match.objects.select_related("home_entry__team", "away_entry__team")
        .filter(pk=match_id)
        .first()
    )
    if match is None:
        raise LineupActionError("Match not found", 404)

    entries = [
        entry
        for entry in (match.home_entry, match.away_entry)
        if entry is not None and entry.team.captain_id == TEMPORARY_CAPTAIN_ID
    ]
    if not entries:
        raise LineupActionError("The temporary captain does not own a team in this match", 403)
    if len(entries) > 1:
        raise LineupActionError("The captain owns both teams; lineup is ambiguous")
    return match, entries[0]


def _lineup_for_captain(lineup_id: int) -> MatchLineup:
    """Загружает состав только если его команда принадлежит временному капитану."""
    lineup = (
        MatchLineup.objects.select_related("match", "entry__team")
        .filter(pk=lineup_id, entry__team__captain_id=TEMPORARY_CAPTAIN_ID)
        .first()
    )
    if lineup is None:
        exists = MatchLineup.objects.filter(pk=lineup_id).exists()
        if not exists:
            raise LineupActionError("Lineup not found", 404)
        raise LineupActionError("The temporary captain does not own this lineup", 403)
    return lineup


def _editable_match(match: Match) -> None:
    """Разрешает редактирование состава до начала матча."""
    if match.status not in (Match.Status.SCHEDULED, Match.Status.LINEUPS_OPEN):
        raise LineupActionError("Lineup can only be changed before the match starts")


def _lineup_payload(match: Match, entry: TournamentEntry, lineup: MatchLineup | None) -> dict:
    """Собирает состав с заявленными игроками и предзаполненным ростером."""
    slots = {}
    if lineup is not None:
        slots = {
            slot.entry_player_id: slot
            for slot in lineup.players.select_related("entry_player__player").all()
        }
    roster = (
        EntryPlayer.objects.filter(entry=entry, status=EntryPlayer.Status.ACTIVE)
        .select_related("player")
        .order_by("number", "id")
    )
    players = []
    for entry_player in roster:
        slot = slots.get(entry_player.id)
        players.append(
            {
                "entry_player_id": entry_player.id,
                "player_id": entry_player.player_id,
                "first_name": entry_player.player.first_name,
                "last_name": entry_player.player.last_name,
                "middle_name": entry_player.player.middle_name,
                "number": entry_player.number,
                "is_starter": slot.is_starter if slot else False,
                "role": slot.role if slot else MatchLineupPlayer.Role.PLAYER,
                "selected": slot is not None,
            }
        )
    return {
        "match_id": match.id,
        "entry_id": entry.id,
        "lineup_id": lineup.id if lineup else None,
        "status": lineup.status if lineup else MatchLineup.Status.DRAFT,
        "players": players,
    }


def get_captain_match_lineup(match_id: int) -> dict:
    """Возвращает сохранённый состав или предзаполненный активным ростером."""
    match, entry = captain_entry_for_match(match_id)
    lineup = MatchLineup.objects.filter(match=match, entry=entry).first()
    return _lineup_payload(match, entry, lineup)


def update_captain_match_lineup(match_id: int, players: list[dict]) -> dict:
    """Заменяет черновой состав указанными активными игроками заявки."""
    with transaction.atomic():
        match, entry = captain_entry_for_match(match_id)
        match = Match.objects.select_for_update().get(pk=match.pk)
        _editable_match(match)
        lineup, _ = MatchLineup.objects.select_for_update().get_or_create(
            match=match,
            entry=entry,
            defaults={"status": MatchLineup.Status.DRAFT},
        )
        if lineup.status not in (MatchLineup.Status.DRAFT, MatchLineup.Status.REJECTED):
            raise LineupActionError("Only a draft or rejected lineup can be edited")

        ids = [player["entry_player_id"] for player in players]
        if len(ids) != len(set(ids)):
            raise LineupActionError("Each roster player can appear only once", 422)
        roster = {
            player.id: player
            for player in EntryPlayer.objects.filter(
                id__in=ids, entry=entry, status=EntryPlayer.Status.ACTIVE
            )
        }
        if len(roster) != len(ids):
            raise LineupActionError("Every lineup player must be active in this team entry", 422)

        lineup.players.all().delete()
        MatchLineupPlayer.objects.bulk_create(
            [
                MatchLineupPlayer(
                    lineup=lineup,
                    entry_player=roster[item["entry_player_id"]],
                    number_snapshot=roster[item["entry_player_id"]].number,
                    is_starter=item["is_starter"],
                    role=item["role"],
                )
                for item in players
            ]
        )
        lineup.status = MatchLineup.Status.DRAFT
        lineup.reject_reason = ""
        lineup.save(update_fields=["status", "reject_reason"])
        return _lineup_payload(match, entry, lineup)


def _lineup_check_data(lineup: MatchLineup) -> dict:
    """Проверяет базовую готовность состава к отправке организатору."""
    slots = list(lineup.players.select_related("entry_player").all())
    starters_count = sum(slot.is_starter for slot in slots)
    captains_count = sum(slot.role == MatchLineupPlayer.Role.CAPTAIN for slot in slots)
    issues = []
    if not slots:
        issues.append("Add at least one player to the lineup")
    if not starters_count:
        issues.append("Select at least one starter")
    if captains_count != 1:
        issues.append("Select exactly one lineup captain")
    if any(slot.entry_player.status != EntryPlayer.Status.ACTIVE for slot in slots):
        issues.append("Remove players who are no longer active in the team entry")
    return {
        "lineup_id": lineup.id,
        "match_id": lineup.match_id,
        "entry_id": lineup.entry_id,
        "status": lineup.status,
        "valid": not issues,
        "issues": issues,
        "player_count": len(slots),
        "starters_count": starters_count,
        "captains_count": captains_count,
    }


def check_captain_lineup(lineup_id: int) -> dict:
    """Возвращает результат проверки доступности состава к отправке."""
    return _lineup_check_data(_lineup_for_captain(lineup_id))


def submit_captain_lineup(lineup_id: int) -> dict:
    """Проверяет и отправляет состав капитана на проверку."""
    with transaction.atomic():
        lineup = _lineup_for_captain(lineup_id)
        lineup = MatchLineup.objects.select_for_update().select_related("match").get(pk=lineup.pk)
        _editable_match(lineup.match)
        if lineup.status not in (MatchLineup.Status.DRAFT, MatchLineup.Status.REJECTED):
            raise LineupActionError("Only a draft or rejected lineup can be submitted")
        result = _lineup_check_data(lineup)
        if not result["valid"]:
            raise LineupActionError("Lineup is incomplete: " + "; ".join(result["issues"]), 422)
        lineup.status = MatchLineup.Status.SUBMITTED
        lineup.reject_reason = ""
        lineup.save(update_fields=["status", "reject_reason"])
        result["status"] = lineup.status
        return result


def submit_captain_match_lineup(match_id: int) -> dict:
    """Находит состав капитана матча и отправляет его после проверки."""
    match, entry = captain_entry_for_match(match_id)
    lineup = MatchLineup.objects.filter(match=match, entry=entry).only("id").first()
    if lineup is None:
        raise LineupActionError("Save a lineup before submitting it", 409)
    return submit_captain_lineup(lineup.id)
