from config.domain_errors import DomainError
from datetime import timedelta
from typing import Any

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils import timezone

from apps.matches.models import (
    Match, MatchEvent, MatchLineup, MatchOfficial, ProtocolCorrectionAudit, Venue,
)
from apps.matches.services.protocol import calculate_match_score
from apps.teams.models import EntryPlayer, TournamentEntry
from apps.tournaments.models import Group, Round, Stage, Tournament




def list_organizer_venues(organization_id: int) -> list[Venue]:
    """Returns venues belonging to the selected organization."""
    from apps.organizations.models import Organization
    if not Organization.objects.filter(pk=organization_id).exists():
        raise DomainError("Organization not found", 404)
    return list(Venue.objects.filter(organization_id=organization_id).order_by("name", "id"))


def create_organizer_venue(organization_id: int, data: dict[str, Any]) -> Venue:
    """Creates a venue in the selected organization."""
    from apps.organizations.models import Organization

    if not Organization.objects.filter(pk=organization_id).exists():
        raise DomainError("Organization not found", 404)
    data = {**data, "name": data["name"].strip()}
    if not data["name"]:
        raise DomainError("Venue name cannot be empty", 422)
    try:
        return Venue.objects.create(organization_id=organization_id, **data)
    except IntegrityError as error:
        raise DomainError("Venue name already exists", 409) from error


def _organizer_venue(organization_id: int, venue_id: int) -> Venue:
    """Loads a venue only within the selected organization."""
    venue = Venue.objects.filter(pk=venue_id, organization_id=organization_id).first()
    if venue is None:
        if not Venue.objects.filter(pk=venue_id).exists():
            raise DomainError("Venue not found", 404)
        raise DomainError("Venue is outside the organizer scope", 403)
    return venue


def get_organizer_venue(organization_id: int, venue_id: int) -> Venue:
    """Returns one venue in the selected organization's scope."""
    return _organizer_venue(organization_id, venue_id)


def update_organizer_venue(organization_id: int, venue_id: int, changes: dict[str, Any]) -> Venue:
    """Updates an organizer-owned venue."""
    venue = _organizer_venue(organization_id, venue_id)
    if not changes:
        raise DomainError("At least one field must be provided", 422)
    if "name" in changes:
        changes["name"] = changes["name"].strip()
        if not changes["name"]:
            raise DomainError("Venue name cannot be empty", 422)
    for field, value in changes.items():
        setattr(venue, field, value)
    try:
        venue.save(update_fields=list(changes))
    except IntegrityError as error:
        raise DomainError("Venue name already exists", 409) from error
    return venue


def delete_organizer_venue(organization_id: int, venue_id: int) -> None:
    """Deletes an organizer-owned venue; referencing matches lose the optional venue."""
    _organizer_venue(organization_id, venue_id).delete()


def list_available_judges(organization_id: int) -> list[dict[str, Any]]:
    """Returns active accounts; the current schema has no judge-role assignment yet."""
    from apps.organizations.models import Organization
    if not Organization.objects.filter(pk=organization_id).exists():
        raise DomainError("Organization not found", 404)
    User = get_user_model()
    users = User.objects.filter(is_active=True).order_by("display_name", "last_name", "first_name", "id")
    return [
        {
            "id": user.id,
            "name": user.display_name or user.get_full_name() or user.username,
        }
        for user in users
    ]


def get_match_lineups_for_judge(match_id: int) -> dict[str, Any]:
    """Returns both participant entries and their submitted match lineups."""
    match = Match.objects.filter(pk=match_id).select_related(
        "home_entry__team", "away_entry__team"
    ).first()
    if match is None:
        raise DomainError("Match not found", 404)
    lineups = {
        lineup.entry_id: lineup
        for lineup in MatchLineup.objects.filter(match=match)
        .prefetch_related("players__entry_player__player")
    }
    items = []
    for entry in (match.home_entry, match.away_entry):
        if entry is None:
            continue
        lineup = lineups.get(entry.id)
        players = []
        if lineup is not None:
            players = [
                {
                    "entry_player_id": slot.entry_player_id,
                    "player_id": slot.entry_player.player_id,
                    "name": " ".join(part for part in (
                        slot.entry_player.player.last_name,
                        slot.entry_player.player.first_name,
                        slot.entry_player.player.middle_name,
                    ) if part),
                    "number": slot.number_snapshot,
                    "is_starter": slot.is_starter,
                    "role": slot.role,
                }
                for slot in lineup.players.all().order_by("number_snapshot", "id")
            ]
        items.append({
            "entry_id": entry.id,
            "team_id": entry.team_id,
            "team_name": entry.team.name,
            "lineup_id": lineup.id if lineup else None,
            "status": lineup.status if lineup else None,
            "reject_reason": lineup.reject_reason if lineup else "",
            "players": players,
        })
    return {"match_id": match.id, "items": items}


def decide_organizer_match_lineup(
    lineup_id: int, status: str, reject_reason: str = ""
) -> MatchLineup:
    """Accepts or rejects a submitted lineup in an organizer-owned match."""
    if status not in (MatchLineup.Status.ACCEPTED, MatchLineup.Status.REJECTED):
        raise DomainError("Lineup decision must be accepted or rejected", 422)
    lineup = MatchLineup.objects.select_related("match__tournament").filter(pk=lineup_id).first()
    if lineup is None:
        raise DomainError("Lineup not found", 404)
    if lineup.status not in (MatchLineup.Status.SUBMITTED, status):
        raise DomainError("Only submitted lineups can be decided", 409)
    if status == MatchLineup.Status.REJECTED and not reject_reason.strip():
        raise DomainError("reject_reason is required when rejecting a lineup", 422)
    lineup.status = status
    lineup.reject_reason = reject_reason.strip() if status == MatchLineup.Status.REJECTED else ""
    lineup.save(update_fields=["status", "reject_reason"])
    return lineup


def _owned_match(match_id: int, *, lock: bool = False) -> Match:
    """Loads a match by ID; request identity scoping is pending authentication."""
    queryset = Match.objects.select_related("tournament", "stage", "round", "venue")
    if lock:
        queryset = queryset.select_for_update()
    match = queryset.filter(pk=match_id).first()
    if match is None:
        raise DomainError("Match not found", 404)
    return match


def _validate_entries(tournament_id: int, home_entry_id: int, away_entry_id: int) -> None:
    """Проверяет, что обе разные команды приняты в этот турнир."""
    if home_entry_id == away_entry_id:
        raise DomainError("Home and away entries must be different", 422)
    accepted_ids = set(
        TournamentEntry.objects.filter(
            tournament_id=tournament_id,
            status=TournamentEntry.Status.ACCEPTED,
            pk__in=[home_entry_id, away_entry_id],
        ).values_list("pk", flat=True)
    )
    if accepted_ids != {home_entry_id, away_entry_id}:
        raise DomainError(
            "home_entry_id and away_entry_id must reference two distinct accepted "
            "entries in this tournament (use TournamentEntry IDs, not Team IDs)",
            422,
        )


def create_organizer_match(tournament_id: int, data: dict[str, Any]) -> Match:
    """Создаёт запланированный матч с проверенными этапом и участниками."""
    tournament = Tournament.objects.filter(pk=tournament_id).first()
    if tournament is None:
        raise DomainError("Tournament not found", 404)

    stage = Stage.objects.filter(pk=data["stage_id"], tournament=tournament).first()
    if stage is None:
        raise DomainError("Stage must belong to the tournament", 422)
    round_id = data.get("round_id")
    if round_id is not None and not Round.objects.filter(pk=round_id, stage=stage).exists():
        raise DomainError("Round must belong to the selected stage", 422)
    group_id = data.get("group_id")
    if group_id is not None and not Group.objects.filter(pk=group_id, stage=stage).exists():
        raise DomainError("Group must belong to the selected stage", 422)
    _validate_entries(tournament.id, data["home_entry_id"], data["away_entry_id"])

    venue_id = data.get("venue_id")
    if venue_id is not None and not tournament.organization.venues.filter(pk=venue_id).exists():
        raise DomainError("Venue must belong to the tournament organization", 422)

    match = Match(
        tournament=tournament,
        stage=stage,
        round_id=round_id,
        group_id=group_id,
        home_entry_id=data["home_entry_id"],
        away_entry_id=data["away_entry_id"],
        venue_id=venue_id,
        scheduled_at=data["scheduled_at"],
        duration_min=data["duration_min"],
        status=Match.Status.SCHEDULED,
    )
    match.scheduled_end = match.scheduled_at + timedelta(minutes=match.duration_min)
    try:
        match.full_clean()
        match.save()
    except ValidationError as error:
        raise DomainError(
            "Match validation failed", 422, validation_error=error
        ) from error
    return match


def reschedule_organizer_match(match_id: int, changes: dict[str, Any]) -> Match:
    """Переносит будущий матч и при необходимости меняет площадку."""
    with transaction.atomic():
        match = _owned_match(match_id, lock=True)
        if match.status not in (
            Match.Status.SCHEDULED,
            Match.Status.LINEUPS_OPEN,
            Match.Status.POSTPONED,
        ):
            raise DomainError("Only scheduled or postponed matches can be moved")
        if "venue_id" in changes and changes["venue_id"] is not None:
            if not match.tournament.organization.venues.filter(pk=changes["venue_id"]).exists():
                raise DomainError("Venue must belong to the tournament organization", 422)
        if "scheduled_at" in changes:
            match.scheduled_at = changes["scheduled_at"]
        if "venue_id" in changes:
            match.venue_id = changes["venue_id"]
        if match.status == Match.Status.POSTPONED:
            match.status = Match.Status.SCHEDULED
        match.save(update_fields=["scheduled_at", "venue", "status"])
        return match


def replace_match_officials(match_id: int, officials: list[dict[str, Any]]) -> dict:
    """Полностью заменяет список официальных лиц матча."""
    with transaction.atomic():
        match = _owned_match(match_id, lock=True)
        if match.status not in (Match.Status.SCHEDULED, Match.Status.LINEUPS_OPEN):
            raise DomainError("Officials can only be changed before the match starts")
        official_ids = [item["official_id"] for item in officials]
        if len(official_ids) != len(set(official_ids)):
            raise DomainError("An official can only be assigned once per match", 422)
        User = get_user_model()
        users = {user.pk: user for user in User.objects.filter(pk__in=official_ids, is_active=True)}
        if len(users) != len(official_ids):
            raise DomainError("Every official_id must belong to an active user", 422)

        MatchOfficial.objects.filter(match=match).delete()
        MatchOfficial.objects.bulk_create(
            [
                MatchOfficial(
                    match=match,
                    official=users[item["official_id"]],
                    role=item["role"],
                )
                for item in officials
            ]
        )
        return {
            "match_id": match.id,
            "officials": [
                {
                    "official_id": item["official_id"],
                    "name": users[item["official_id"]].display_name
                    or users[item["official_id"]].get_full_name()
                    or users[item["official_id"]].username,
                    "role": item["role"],
                }
                for item in officials
            ],
        }


def correct_organizer_match_event(
    match_id: int,
    actor_user_id: int,
    event_id: Any,
    action: str,
    replacement: dict[str, Any] | None,
    reason: str,
) -> dict:
    """Audits a reasoned correction while preserving the append-only protocol."""
    reason = reason.strip()
    if not reason:
        raise DomainError("A correction reason is required", 422)
    if action not in ("void", "replace"):
        raise DomainError("action must be void or replace", 422)
    if (action == "replace") != (replacement is not None):
        raise DomainError("replacement is required only for action=replace", 422)

    with transaction.atomic():
        match = _owned_match(match_id, lock=True)
        if match.home_entry_id is None or match.away_entry_id is None:
            raise DomainError("Both match participants must be assigned", 409)
        target = MatchEvent.objects.filter(pk=event_id, match=match).first()
        if target is None:
            exists = MatchEvent.objects.filter(pk=event_id).exists()
            if exists:
                raise DomainError("Event belongs to another match", 404)
            raise DomainError("Event not found", 404)
        if target.type in (MatchEvent.Type.VOID, MatchEvent.Type.REVIEW_OK):
            raise DomainError("Only original protocol events can be corrected", 409)
        if MatchEvent.objects.filter(
            match=match, type=MatchEvent.Type.VOID, target_event=target
        ).exists():
            raise DomainError("Event has already been voided", 409)

        if replacement is not None:
            replacement = dict(replacement)
            if replacement.get("clock_ms") is None and (
                replacement.get("minute") is not None
                or replacement.get("second") is not None
            ):
                replacement["clock_ms"] = (replacement.get("minute") or 0) * 60_000 + (
                    replacement.get("second") or 0
                ) * 1_000
            if replacement.get("clock_ms") is not None:
                replacement["minute"] = replacement["clock_ms"] // 60_000
                replacement["second"] = (replacement["clock_ms"] % 60_000) // 1_000
            entry_id = replacement.get("entry_id")
            player_id = replacement.get("entry_player_id")
            related_player_id = replacement.get("related_entry_player_id")
            participant_ids = {match.home_entry_id, match.away_entry_id}
            if entry_id is not None and entry_id not in participant_ids:
                raise DomainError("Event entry must be a match participant", 422)
            if replacement["type"] in (MatchEvent.Type.GOAL, MatchEvent.Type.OWN_GOAL) and entry_id is None:
                raise DomainError("Goal events require entry_id", 422)
            if player_id is not None and (
                entry_id is None
                or not EntryPlayer.objects.filter(pk=player_id, entry_id=entry_id).exists()
            ):
                raise DomainError("entry_player_id must belong to entry_id", 422)
            if replacement["type"] == MatchEvent.Type.SUBSTITUTION:
                if player_id is None or related_player_id is None or player_id == related_player_id:
                    raise DomainError("Substitution requires two different players", 422)
                if not EntryPlayer.objects.filter(pk=related_player_id, entry_id=entry_id).exists():
                    raise DomainError("related_entry_player_id must belong to entry_id", 422)

        last_seq = MatchEvent.objects.filter(match=match).aggregate(value=Max("seq"))["value"] or 0
        void_event = MatchEvent.objects.create(
            match=match,
            seq=last_seq + 1,
            type=MatchEvent.Type.VOID,
            target_event=target,
            source=MatchEvent.Source.ORGANIZER,
        )
        replacement_event = None
        if replacement is not None:
            replacement_event = MatchEvent.objects.create(
                match=match,
                seq=last_seq + 2,
                type=replacement["type"],
                entry_id=replacement.get("entry_id"),
                player_id=replacement.get("entry_player_id"),
                related_player_id=replacement.get("related_entry_player_id"),
                period=replacement.get("period"),
                clock_ms=replacement.get("clock_ms"),
                minute=replacement.get("minute"),
                second=replacement.get("second"),
                source=MatchEvent.Source.ORGANIZER,
            )
        ProtocolCorrectionAudit.objects.create(
            match=match,
            target_event=target,
            void_event=void_event,
            replacement_event=replacement_event,
            organization_id=match.tournament.organization_id,
            actor_reference=f"user:{actor_user_id}",
            reason=reason,
        )

        match.home_score, match.away_score = calculate_match_score(match)
        update_fields = ["home_score", "away_score"]
        if target.type == MatchEvent.Type.FINISH or (
            replacement is not None and replacement["type"] == MatchEvent.Type.FINISH
        ):
            if replacement is not None and replacement["type"] == MatchEvent.Type.FINISH:
                match.status = (
                    Match.Status.CONFIRMED
                    if match.status == Match.Status.CONFIRMED
                    else Match.Status.FINISHED
                )
                match.finished_at = match.finished_at or timezone.now()
            else:
                match.status = Match.Status.LIVE
                match.finished_at = None
                match.confirmed_at = None
                update_fields.append("confirmed_at")
            update_fields.extend(["status", "finished_at"])
        match.save(update_fields=update_fields)

        if replacement_event is not None:
            replacement_event = MatchEvent.objects.select_related("player__player").get(
                pk=replacement_event.pk
            )
        return {
            "match_id": match.id,
            "voided_event_id": str(target.id),
            "replacement_event": replacement_event,
            "home_score": match.home_score,
            "away_score": match.away_score,
            "status": match.status,
            "reason": reason,
        }
