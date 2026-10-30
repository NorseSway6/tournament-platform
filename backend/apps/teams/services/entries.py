from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.common.errors import (
    ConflictError,
    DomainValidationError,
    ForbiddenError,
    NotFoundError,
)
from apps.teams.models import EntryPlayer, Player, Team, TournamentEntry
from apps.tournaments.models import Tournament


def get_captain_entry_players(captain_id: int, entry_id: int) -> dict:
    """Возвращает ростер заявки только если заявка принадлежит команде капитана."""
    entry = TournamentEntry.objects.filter(pk=entry_id, team__captain_id=captain_id).first()
    if entry is None:
        if not TournamentEntry.objects.filter(pk=entry_id).exists():
            raise NotFoundError("Entry not found")
        raise ForbiddenError("The authenticated captain does not own this entry")
    players = (
        EntryPlayer.objects.filter(entry=entry).select_related("player").order_by("number", "id")
    )
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


def create_captain_tournament_entry(
    captain_id: int, tournament_id: int, team_id: int
) -> TournamentEntry:
    """Создаёт заявку принадлежащей капитану команды в открытый турнир."""
    tournament = Tournament.objects.filter(pk=tournament_id).first()
    if tournament is None:
        raise NotFoundError("Tournament not found")
    if tournament.status != Tournament.Status.REGISTRATION:
        raise ConflictError("Tournament is not accepting entries", code="registration_closed")
    if tournament.registration_deadline and tournament.registration_deadline < timezone.now():
        raise ConflictError(
            "Tournament registration deadline has passed", code="registration_deadline_passed"
        )

    team = Team.objects.filter(pk=team_id, captain_id=captain_id).first()
    if team is None:
        exists = Team.objects.filter(pk=team_id).exists()
        if not exists:
            raise NotFoundError("Team not found")
        raise ForbiddenError("The authenticated captain does not own this team")
    try:
        with transaction.atomic():
            return TournamentEntry.objects.create(tournament=tournament, team=team)
    except IntegrityError as error:
        raise ConflictError(
            "This team already has an entry in the tournament", code="entry_exists"
        ) from error


def update_captain_entry_players(captain_id: int, entry_id: int, players: list[dict]) -> dict:
    """Полностью заменяет активный ростер заявки данными капитана."""
    with transaction.atomic():
        entry = (
            TournamentEntry.objects.select_for_update()
            .select_related("tournament", "team")
            .filter(pk=entry_id, team__captain_id=captain_id)
            .first()
        )
        if entry is None:
            exists = TournamentEntry.objects.filter(pk=entry_id).exists()
            if not exists:
                raise NotFoundError("Entry not found")
            raise ForbiddenError("The authenticated captain does not own this entry")
        if entry.status not in (
            TournamentEntry.Status.PENDING,
            TournamentEntry.Status.ACCEPTED,
        ):
            raise ConflictError("Players cannot be changed for this entry", code="roster_closed")
        if entry.tournament.status != Tournament.Status.REGISTRATION:
            raise ConflictError(
                "Roster can only be changed during registration", code="roster_closed"
            )
        deadline = entry.tournament.registration_deadline
        if deadline is not None and deadline < timezone.now():
            raise ConflictError("Roster registration deadline has passed", code="roster_closed")

        numbers = [player["number"] for player in players]
        if len(numbers) != len(set(numbers)):
            raise DomainValidationError("Jersey numbers must be unique within the entry")
        player_ids = [player["player_id"] for player in players if player.get("player_id")]
        if len(player_ids) != len(set(player_ids)):
            raise DomainValidationError("A player can appear only once in the entry")

        existing_players = {
            player.id: player for player in Player.objects.filter(pk__in=player_ids)
        }
        if len(existing_players) != len(player_ids):
            raise DomainValidationError("One or more player_id values do not exist")
        for player_id in player_ids:
            player = existing_players[player_id]
            if player.user_id is not None:
                if player.user_id != captain_id:
                    raise ForbiddenError(
                        "A player linked to another user cannot be added",
                        code="player_not_owned",
                    )
            elif player.created_by_id is not None:
                if player.created_by_id != captain_id:
                    raise ForbiddenError(
                        "A player created by another captain cannot be added",
                        code="player_not_owned",
                    )
            elif not EntryPlayer.objects.filter(entry=entry, player_id=player_id).exists():
                raise ForbiddenError(
                    "A player profile without an owner cannot be added",
                    code="player_not_owned",
                )
        if (
            EntryPlayer.objects.filter(
                entry__tournament=entry.tournament,
                player_id__in=player_ids,
                status=EntryPlayer.Status.ACTIVE,
            )
            .exclude(entry=entry)
            .exists()
        ):
            raise ConflictError(
                "A player can only be active in one entry per tournament",
                code="player_already_in_tournament",
            )

        for item in players:
            first_name = (item.get("first_name") or "").strip()
            last_name = (item.get("last_name") or "").strip()
            if item.get("player_id") is None and not (first_name and last_name):
                raise DomainValidationError("New players require first_name and last_name")

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
                    created_by_id=captain_id,
                )
            membership = EntryPlayer.objects.filter(entry=entry, player=player).first()
            if membership is None:
                membership = EntryPlayer(entry=entry, player=player)
            membership.number = item["number"]
            membership.status = EntryPlayer.Status.ACTIVE
            try:
                membership.save()
            except IntegrityError as error:
                raise ConflictError(
                    "A player can only be active in one entry per tournament",
                    code="player_already_in_tournament",
                ) from error
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
