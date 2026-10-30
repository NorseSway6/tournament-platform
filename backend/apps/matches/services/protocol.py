from datetime import timedelta
from typing import Any
from uuid import UUID, uuid4

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.common.errors import (
    ConflictError,
    DomainValidationError,
    NotFoundError,
    ResourceLockedError,
)
from apps.matches.models import Match, MatchEvent
from apps.teams.models import EntryPlayer

# Срок жизни аренды матча и поля строки Match, в которых она хранится.
MATCH_LEASE_SECONDS = 90
LEASE_FIELDS = ["lease_token", "lease_judge", "lease_expires_at"]


def _get_match_for_update(match_id: int) -> Match:
    """Загружает строку матча под блокировкой для последовательных изменений."""
    match = Match.objects.select_for_update().filter(pk=match_id).first()
    if match is None:
        raise NotFoundError("Match not found")
    return match


def _clear_expired_lease(match: Match) -> None:
    """Сбрасывает в памяти истёкшую аренду перед дальнейшими проверками."""
    if match.lease_expires_at is not None and match.lease_expires_at <= timezone.now():
        match.lease_token = None
        match.lease_judge = None
        match.lease_expires_at = None


def _renew_lease(match: Match) -> None:
    """Продлевает аренду матча после успешной операции судьи."""
    match.lease_expires_at = timezone.now() + timedelta(seconds=MATCH_LEASE_SECONDS)
    match.save(update_fields=["lease_expires_at"])


def _require_lease(match: Match, token: UUID, judge_id: int) -> None:
    """Проверяет токен аренды и владельца для изменения протокола матча."""
    if (
        match.lease_token is None
        or match.lease_expires_at is None
        or match.lease_expires_at <= timezone.now()
    ):
        raise ResourceLockedError("Lease is missing or expired", code="lease_expired")
    if match.lease_token != token or match.lease_judge_id != judge_id:
        raise ResourceLockedError("Lease token or owner does not match", code="lease_invalid")


def acquire_match_lease(match_id: int, judge_id: int) -> dict[str, Any]:
    """Открывает матч для указанного судьи или возвращает его текущую аренду."""
    with transaction.atomic():
        match = _get_match_for_update(match_id)
        _clear_expired_lease(match)
        if match.lease_token is not None and match.lease_judge_id != judge_id:
            raise ConflictError("Match already has an active lease", code="lease_taken")
        if match.status in (
            Match.Status.CANCELLED,
            Match.Status.CONFIRMED,
            Match.Status.TECHNICAL,
            Match.Status.POSTPONED,
        ):
            raise ConflictError(
                "This match cannot be leased in its current status", code="lease_status_invalid"
            )
        if match.home_entry_id is None or match.away_entry_id is None:
            raise ConflictError(
                "Both match participants must be assigned before leasing",
                code="participants_missing",
            )

        if match.lease_token is None:
            match.lease_token = uuid4()
            match.lease_judge_id = judge_id
        match.lease_expires_at = timezone.now() + timedelta(seconds=MATCH_LEASE_SECONDS)

        fields_to_update = set(LEASE_FIELDS)
        if match.status in (Match.Status.SCHEDULED, Match.Status.LINEUPS_OPEN):
            match.status = Match.Status.LIVE
            match.started_at = match.started_at or timezone.now()
            match.home_score = match.home_score if match.home_score is not None else 0
            match.away_score = match.away_score if match.away_score is not None else 0
            fields_to_update.update({"status", "started_at", "home_score", "away_score"})
        elif match.status == Match.Status.LIVE and match.home_score is None:
            match.home_score = 0
            match.away_score = 0
            fields_to_update.update({"home_score", "away_score"})

        match.save(update_fields=sorted(fields_to_update))
        return {
            "match_id": match.id,
            "lease_token": match.lease_token,
            "expires_at": match.lease_expires_at,
            "expires_in_seconds": MATCH_LEASE_SECONDS,
        }


def renew_match_lease(match_id: int, judge_id: int, lease_token: UUID) -> dict[str, Any]:
    """Extends the active judge lease without changing its token."""
    with transaction.atomic():
        match = _get_match_for_update(match_id)
        _require_lease(match, lease_token, judge_id)
        _renew_lease(match)
        return {
            "match_id": match_id,
            "lease_token": match.lease_token,
            "expires_at": match.lease_expires_at,
            "expires_in_seconds": MATCH_LEASE_SECONDS,
        }


def release_match_lease(match_id: int, judge_id: int, lease_token: UUID) -> dict[str, Any]:
    """Releases the active lease while leaving the match protocol intact."""
    with transaction.atomic():
        match = _get_match_for_update(match_id)
        _require_lease(match, lease_token, judge_id)
        match.lease_token = None
        match.lease_judge = None
        match.lease_expires_at = None
        match.save(update_fields=LEASE_FIELDS)
        return {"match_id": match_id, "released": True}


def takeover_match_lease(match_id: int, judge_id: int) -> dict[str, Any]:
    """Takes over a live match lease only when it is absent or already expired."""
    with transaction.atomic():
        match = _get_match_for_update(match_id)
        if match.status != Match.Status.LIVE:
            raise ConflictError("Only a live match can be taken over", code="match_not_live")
        _clear_expired_lease(match)
        if match.lease_token is not None:
            raise ConflictError(
                "An active lease cannot be taken over; wait for expiry or ask an organizer",
                code="lease_active",
            )
        match.lease_token = uuid4()
        match.lease_judge_id = judge_id
        match.lease_expires_at = timezone.now() + timedelta(seconds=MATCH_LEASE_SECONDS)
        match.save(update_fields=LEASE_FIELDS)
        return {
            "match_id": match_id,
            "lease_token": match.lease_token,
            "expires_at": match.lease_expires_at,
            "expires_in_seconds": MATCH_LEASE_SECONDS,
        }


def judge_match_ids(judge_id: int) -> set[int]:
    """Возвращает матчи, арендованные указанным судьёй и ещё не истёкшие."""
    return set(
        Match.objects.filter(
            lease_judge_id=judge_id,
            lease_token__isnull=False,
            lease_expires_at__gt=timezone.now(),
        ).values_list("id", flat=True)
    )


def _validate_event(match: Match, event_data: dict[str, Any]) -> MatchEvent | None:
    """Проверяет участников, игрока и целевое событие протокола."""
    entry_id = event_data["entry_id"]
    player_id = event_data["entry_player_id"]
    related_player_id = event_data["related_entry_player_id"]
    target_event_id = event_data["target_event_id"]
    event_type = event_data["type"]
    participant_ids = {match.home_entry_id, match.away_entry_id} - {None}

    if entry_id is not None and entry_id not in participant_ids:
        raise DomainValidationError("Event entry must be one of the match participants")
    if event_type in (MatchEvent.Type.GOAL, MatchEvent.Type.OWN_GOAL) and entry_id is None:
        raise DomainValidationError("Goal events require entry_id")
    if player_id is not None and (
        entry_id is None or not EntryPlayer.objects.filter(pk=player_id, entry_id=entry_id).exists()
    ):
        raise DomainValidationError("entry_player_id must belong to entry_id")
    if related_player_id is not None and (
        entry_id is None
        or not EntryPlayer.objects.filter(pk=related_player_id, entry_id=entry_id).exists()
    ):
        raise DomainValidationError("related_entry_player_id must belong to entry_id")
    if event_type == MatchEvent.Type.SUBSTITUTION:
        if player_id is None or related_player_id is None:
            raise DomainValidationError("Substitution events require both player IDs")
        if player_id == related_player_id:
            raise DomainValidationError("A substitution requires two different players")
    elif related_player_id is not None:
        raise DomainValidationError("related_entry_player_id is only valid for substitution")

    if event_type in (MatchEvent.Type.VOID, MatchEvent.Type.REVIEW_OK):
        if target_event_id is None:
            raise DomainValidationError("Revision events require target_event_id")
        target = MatchEvent.objects.filter(pk=target_event_id, match=match).first()
        if target is None or target.type in (MatchEvent.Type.VOID, MatchEvent.Type.REVIEW_OK):
            raise DomainValidationError("target_event_id must reference a base event in this match")
        return target
    if target_event_id is not None:
        raise DomainValidationError("target_event_id is only valid for revision events")
    return None


def calculate_match_score(match: Match) -> tuple[int, int]:
    """Рассчитывает счёт по голам и отменам из журнала событий."""
    events = list(
        MatchEvent.objects.filter(match=match).values("id", "type", "entry_id", "target_event_id")
    )
    voided_ids = {
        event["target_event_id"]
        for event in events
        if event["type"] == MatchEvent.Type.VOID and event["target_event_id"] is not None
    }
    scores = {match.home_entry_id: 0, match.away_entry_id: 0}
    for event in events:
        if event["type"] not in (MatchEvent.Type.GOAL, MatchEvent.Type.OWN_GOAL):
            continue
        if event["id"] in voided_ids:
            continue
        entry_id = event["entry_id"]
        if entry_id not in scores:
            continue
        scoring_entry_id = entry_id
        if event["type"] == MatchEvent.Type.OWN_GOAL:
            scoring_entry_id = (
                match.away_entry_id if entry_id == match.home_entry_id else match.home_entry_id
            )
        scores[scoring_entry_id] += 1
    return scores[match.home_entry_id], scores[match.away_entry_id]


def append_match_event(
    match_id: int, judge_id: int, event_data: dict[str, Any]
) -> tuple[dict[str, Any], bool]:
    """Appends or deduplicates one event and returns updated score and sequence."""
    lease_token = event_data.pop("lease_token")
    if event_data["clock_ms"] is None and (
        event_data["minute"] is not None or event_data["second"] is not None
    ):
        event_data["clock_ms"] = (event_data["minute"] or 0) * 60_000 + (
            event_data["second"] or 0
        ) * 1_000
    if event_data["clock_ms"] is not None:
        event_data["minute"] = event_data["clock_ms"] // 60_000
        event_data["second"] = (event_data["clock_ms"] % 60_000) // 1_000
    with transaction.atomic():
        match = _get_match_for_update(match_id)
        _require_lease(match, lease_token, judge_id)
        existing = MatchEvent.objects.filter(pk=event_data["id"]).first()
        if existing is None and event_data["client_seq"] is not None:
            existing = MatchEvent.objects.filter(
                match_id=match_id,
                device_id=event_data["device_id"],
                client_seq=event_data["client_seq"],
            ).first()
        if existing is not None:
            fields_match = (
                existing.match_id == match_id
                and existing.device_id == event_data["device_id"]
                and existing.client_seq == event_data["client_seq"]
                and existing.type == event_data["type"]
                and existing.entry_id == event_data["entry_id"]
                and existing.player_id == event_data["entry_player_id"]
                and existing.related_player_id == event_data["related_entry_player_id"]
                and existing.period == event_data["period"]
                and existing.clock_ms == event_data["clock_ms"]
                and existing.needs_review == event_data["needs_review"]
                and existing.minute == event_data["minute"]
                and existing.second == event_data["second"]
                and existing.client_created_at == event_data["client_created_at"]
                and existing.target_event_id == event_data["target_event_id"]
            )
            if not fields_match:
                raise ConflictError(
                    "Device sequence or event ID already exists with different data",
                    code="event_conflict",
                )
            _renew_lease(match)
            return _event_append_result(existing, match), False

        if match.status != Match.Status.LIVE:
            raise ConflictError("Events can only be added to a live match", code="match_not_live")
        _validate_event(match, event_data)
        last_seq = MatchEvent.objects.filter(match=match).aggregate(value=Max("seq"))["value"] or 0
        event = MatchEvent.objects.create(
            id=event_data["id"],
            match=match,
            seq=last_seq + 1,
            device_id=event_data["device_id"],
            client_seq=event_data["client_seq"],
            type=event_data["type"],
            entry_id=event_data["entry_id"],
            player_id=event_data["entry_player_id"],
            related_player_id=event_data["related_entry_player_id"],
            period=event_data["period"],
            clock_ms=event_data["clock_ms"],
            minute=event_data["minute"],
            second=event_data["second"],
            client_created_at=event_data["client_created_at"],
            target_event_id=event_data["target_event_id"],
            needs_review=event_data["needs_review"],
            source=MatchEvent.Source.JUDGE,
        )
        match.home_score, match.away_score = calculate_match_score(match)
        fields_to_update = ["home_score", "away_score"]
        if event.type == MatchEvent.Type.FINISH:
            match.status = Match.Status.FINISHED
            match.finished_at = timezone.now()
            fields_to_update.extend(["status", "finished_at"])
        match.save(update_fields=fields_to_update)
        _renew_lease(match)
        event.voided = False
        return _event_append_result(event, match), True


def _event_append_result(event: MatchEvent, match: Match) -> dict[str, Any]:
    """Builds the stable append response envelope from persisted match state."""
    match.refresh_from_db(fields=["home_score", "away_score"])
    last_seq = (
        MatchEvent.objects.filter(match_id=match.id).aggregate(value=Max("seq"))["value"] or 0
    )
    if not hasattr(event, "voided"):
        event.voided = MatchEvent.objects.filter(
            type=MatchEvent.Type.VOID, target_event_id=event.id
        ).exists()
    return {
        "event": event,
        "home_score": match.home_score,
        "away_score": match.away_score,
        "last_seq": last_seq,
    }


def append_match_events(
    match_id: int, judge_id: int, events_data: list[dict[str, Any]], lease_token: UUID
) -> tuple[dict[str, Any], bool]:
    """Appends a batch atomically and returns its event list and latest score."""
    results = []
    created_any = False
    with transaction.atomic():
        match = _get_match_for_update(match_id)
        _require_lease(match, lease_token, judge_id)
        for item in events_data:
            result, created = append_match_event(
                match_id, judge_id, {**item, "lease_token": lease_token}
            )
            results.append(result["event"])
            created_any = created_any or created
        match = _get_match_for_update(match_id)
        latest = (
            _event_append_result(results[-1], match)
            if results
            else {
                "home_score": match.home_score,
                "away_score": match.away_score,
                "last_seq": MatchEvent.objects.filter(match=match).aggregate(value=Max("seq"))[
                    "value"
                ]
                or 0,
            }
        )
        return {
            "items": results,
            "home_score": latest["home_score"],
            "away_score": latest["away_score"],
            "last_seq": latest["last_seq"],
        }, created_any


def confirm_match(match_id: int, judge_id: int, lease_token: UUID) -> Match:
    """Подтверждает завершённый матч при действующем lease-token."""
    with transaction.atomic():
        match = _get_match_for_update(match_id)
        _require_lease(match, lease_token, judge_id)
        if match.status == Match.Status.CONFIRMED:
            _renew_lease(match)
            return match
        if match.status != Match.Status.FINISHED:
            raise ConflictError("Only a finished match can be confirmed", code="match_not_finished")
        match.status = Match.Status.CONFIRMED
        match.confirmed_at = timezone.now()
        match.save(update_fields=["status", "confirmed_at"])
        _renew_lease(match)
        return match
