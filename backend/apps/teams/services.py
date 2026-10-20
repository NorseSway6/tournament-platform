from django.db import IntegrityError, transaction
from django.utils import timezone

from config.temporary_ids import TEMPORARY_CAPTAIN_ID
from apps.teams.models import EntryPlayer, Player, Team, TournamentEntry
from apps.tournaments.models import Tournament


class CaptainActionError(Exception):
    """Сообщает об ошибке операции капитана с командой или заявкой."""

    def __init__(self, message: str, status_code: int = 409):
        super().__init__(message)
        self.status_code = status_code


class OrganizerEntryError(Exception):
    """Сообщает об ошибке решения организатора по заявке."""

    def __init__(self, message: str, status_code: int = 409):
        super().__init__(message)
        self.status_code = status_code


def decide_organizer_entry(
    entry_id: int, status: str, decision_comment: str = ""
) -> TournamentEntry:
    """Принимает или отклоняет заявку; organization authorization is not available yet."""
    if status not in (TournamentEntry.Status.ACCEPTED, TournamentEntry.Status.REJECTED):
        raise OrganizerEntryError("Entry decision must be accepted or rejected", 422)
    with transaction.atomic():
        entry = (
            TournamentEntry.objects.select_for_update()
            .select_related("tournament")
            .filter(pk=entry_id)
            .first()
        )
        if entry is None:
            exists = TournamentEntry.objects.filter(pk=entry_id).exists()
            if not exists:
                raise OrganizerEntryError("Entry not found", 404)
        if entry.status == status:
            return entry
        if entry.status != TournamentEntry.Status.PENDING:
            raise OrganizerEntryError("Only pending entries can be decided", 409)
        if entry.tournament.status not in (
            Tournament.Status.REGISTRATION,
            Tournament.Status.ONGOING,
        ):
            raise OrganizerEntryError("Entries cannot be decided for this tournament", 409)
        entry.status = status
        entry.decision_comment = decision_comment.strip()
        entry.save(update_fields=["status", "decision_comment"])
        return entry


def create_captain_team(data: dict) -> Team:
    """Создаёт команду, назначая временного капитана её владельцем."""
    name = data["name"].strip()
    if not name:
        raise CaptainActionError("Team name cannot be empty", 422)
    return Team.objects.create(
        name=name,
        city=data.get("city", "").strip(),
        captain_id=TEMPORARY_CAPTAIN_ID,
    )


def list_captain_teams() -> list[Team]:
    """Возвращает команды временного капитана вместе с публичными заявками."""
    return list(
        Team.objects.filter(captain_id=TEMPORARY_CAPTAIN_ID)
        .prefetch_related("entries__tournament")
        .order_by("name", "id")
    )


def update_captain_team(team_id: int, changes: dict) -> Team:
    """Изменяет название и город команды, принадлежащей временному капитану."""
    team = Team.objects.filter(pk=team_id, captain_id=TEMPORARY_CAPTAIN_ID).first()
    if team is None:
        if not Team.objects.filter(pk=team_id).exists():
            raise CaptainActionError("Team not found", 404)
        raise CaptainActionError("The temporary captain does not own this team", 403)
    if not changes:
        raise CaptainActionError("At least one field must be provided", 422)
    if "name" in changes:
        name = changes["name"].strip()
        if not name:
            raise CaptainActionError("Team name cannot be empty", 422)
        team.name = name
    if "city" in changes:
        team.city = (changes["city"] or "").strip()
    team.save(update_fields=["name", "city", "updated_at"])
    return team


def get_captain_entry_players(entry_id: int) -> dict:
    """Возвращает ростер заявки только если заявка принадлежит команде капитана."""
    entry = TournamentEntry.objects.filter(
        pk=entry_id, team__captain_id=TEMPORARY_CAPTAIN_ID
    ).first()
    if entry is None:
        if not TournamentEntry.objects.filter(pk=entry_id).exists():
            raise CaptainActionError("Entry not found", 404)
        raise CaptainActionError("The temporary captain does not own this entry", 403)
    players = EntryPlayer.objects.filter(entry=entry).select_related("player").order_by("number", "id")
    return {
        "entry_id": entry.id,
        "players": [
            {
                "entry_player_id": item.id,
                "player_id": item.player_id,
                "first_name": item.player.first_name,
                "last_name": item.player.last_name,
                "middle_name": item.player.middle_name,
                "birth_date": item.player.birth_date,
                "number": item.number,
                "status": item.status,
            }
            for item in players
        ],
    }


def create_captain_tournament_entry(tournament_id: int, team_id: int) -> TournamentEntry:
    """Создаёт заявку принадлежащей капитану команды в открытый турнир."""
    tournament = Tournament.objects.filter(pk=tournament_id).first()
    if tournament is None:
        raise CaptainActionError("Tournament not found", 404)
    if tournament.status != Tournament.Status.REGISTRATION:
        raise CaptainActionError("Tournament is not accepting entries", 409)
    if tournament.registration_deadline and tournament.registration_deadline < timezone.now():
        raise CaptainActionError("Tournament registration deadline has passed", 409)

    team = Team.objects.filter(pk=team_id, captain_id=TEMPORARY_CAPTAIN_ID).first()
    if team is None:
        exists = Team.objects.filter(pk=team_id).exists()
        if not exists:
            raise CaptainActionError("Team not found", 404)
        raise CaptainActionError("The temporary captain does not own this team", 403)
    try:
        with transaction.atomic():
            return TournamentEntry.objects.create(tournament=tournament, team=team)
    except IntegrityError as error:
        raise CaptainActionError("This team already has an entry in the tournament", 409) from error


def update_captain_entry_players(entry_id: int, players: list[dict]) -> dict:
    """Полностью заменяет активный ростер заявки данными капитана."""
    with transaction.atomic():
        entry = (
            TournamentEntry.objects.select_for_update()
            .select_related("tournament", "team")
            .filter(pk=entry_id, team__captain_id=TEMPORARY_CAPTAIN_ID)
            .first()
        )
        if entry is None:
            exists = TournamentEntry.objects.filter(pk=entry_id).exists()
            if not exists:
                raise CaptainActionError("Entry not found", 404)
            raise CaptainActionError("The temporary captain does not own this entry", 403)
        if entry.status not in (TournamentEntry.Status.PENDING, TournamentEntry.Status.ACCEPTED):
            raise CaptainActionError("Players cannot be changed for this entry", 409)
        if entry.tournament.status == Tournament.Status.FINISHED:
            raise CaptainActionError("Players cannot be changed after the tournament has finished", 409)

        numbers = [player["number"] for player in players]
        if len(numbers) != len(set(numbers)):
            raise CaptainActionError("Jersey numbers must be unique within the entry", 422)
        player_ids = [player["player_id"] for player in players if player.get("player_id")]
        if len(player_ids) != len(set(player_ids)):
            raise CaptainActionError("A player can appear only once in the entry", 422)

        existing_players = {
            player.id: player
            for player in Player.objects.filter(pk__in=player_ids)
        }
        if len(existing_players) != len(player_ids):
            raise CaptainActionError("One or more player_id values do not exist", 422)
        if Player.objects.filter(pk__in=player_ids, user__isnull=False).exclude(
            user_id=TEMPORARY_CAPTAIN_ID
        ).exists():
            raise CaptainActionError("A player linked to another user cannot be added", 403)

        for item in players:
            first_name = (item.get("first_name") or "").strip()
            last_name = (item.get("last_name") or "").strip()
            if item.get("player_id") is None and not (first_name and last_name):
                raise CaptainActionError(
                    "New players require first_name and last_name", 422
                )

        # Сначала освобождаем номера: это позволяет капитану менять номера местами.
        EntryPlayer.objects.filter(entry=entry, status=EntryPlayer.Status.ACTIVE).update(
            status=EntryPlayer.Status.REMOVED
        )

        updated = []
        for item in players:
            player = existing_players.get(item.get("player_id"))
            if player is None:
                player = Player.objects.create(
                    first_name=(item.get("first_name") or "").strip(),
                    last_name=(item.get("last_name") or "").strip(),
                    middle_name=(item.get("middle_name") or "").strip(),
                    birth_date=item.get("birth_date"),
                )
            membership = EntryPlayer.objects.filter(entry=entry, player=player).first()
            if membership is None:
                membership = EntryPlayer(entry=entry, player=player)
            membership.number = item["number"]
            membership.status = EntryPlayer.Status.ACTIVE
            membership.save()
            updated.append(membership)

        return {
            "entry_id": entry.id,
            "players": [
                {
                    "entry_player_id": membership.id,
                    "player_id": membership.player_id,
                    "first_name": membership.player.first_name,
                    "last_name": membership.player.last_name,
                    "middle_name": membership.player.middle_name,
                    "birth_date": membership.player.birth_date,
                    "number": membership.number,
                    "status": membership.status,
                }
                for membership in updated
            ],
        }
