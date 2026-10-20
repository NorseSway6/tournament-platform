from dataclasses import dataclass
from datetime import timedelta
from threading import RLock
from typing import Any
from uuid import UUID, uuid4

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from config.temporary_ids import TEMPORARY_JUDGE_ID
from apps.matches.models import Match, MatchEvent
from apps.teams.models import EntryPlayer


# Временная личность для judge-среза до появления аутентификации и назначений.
MATCH_LEASE_SECONDS = 90


class MatchActionError(Exception):
    """Ошибка бизнес-операции над матчем с HTTP-нейтральным статусом."""

    def __init__(self, message: str, status_code: int = 409):
        super().__init__(message)
        self.status_code = status_code


@dataclass
class ActiveLease:
    token: UUID
    judge_id: int
    expires_at: Any


_active_leases: dict[int, ActiveLease] = {}
_lease_lock = RLock()


def _get_match_for_update(match_id: int) -> Match:
    """Загружает строку матча под блокировкой для последовательных изменений."""
    match = Match.objects.select_for_update().filter(pk=match_id).first()
    if match is None:
        raise MatchActionError("Match not found", status_code=404)
    return match


def _lease_for_match(match_id: int) -> ActiveLease | None:
    """Возвращает lease матча и очищает его, если срок уже истёк."""
    lease = _active_leases.get(match_id)
    if lease is not None and lease.expires_at <= timezone.now():
        _active_leases.pop(match_id, None)
        return None
    return lease


def _renew_lease(match_id: int, lease: ActiveLease) -> ActiveLease:
    """Продлевает lease после успешно выполненной операции судьи."""
    lease.expires_at = timezone.now() + timedelta(seconds=MATCH_LEASE_SECONDS)
    _active_leases[match_id] = lease
    return lease


def _require_lease(match_id: int, token: UUID) -> ActiveLease:
    """Проверяет токен активного lease для изменения протокола матча."""
    lease = _lease_for_match(match_id)
    if lease is None or lease.token != token:
        raise MatchActionError("Lease is missing, expired, or invalid", status_code=423)
    return lease


def acquire_match_lease(match_id: int) -> dict[str, Any]:
    """Открывает матч для работы судьи или возвращает его активный lease."""
    with _lease_lock, transaction.atomic():
        match = _get_match_for_update(match_id)
        lease = _lease_for_match(match_id)
        if lease is not None and lease.judge_id != TEMPORARY_JUDGE_ID:
            raise MatchActionError("Match already has an active lease")
        if match.status in (
            Match.Status.CANCELLED,
            Match.Status.CONFIRMED,
            Match.Status.TECHNICAL,
            Match.Status.POSTPONED,
        ):
            raise MatchActionError("This match cannot be leased in its current status")
        if match.home_entry_id is None or match.away_entry_id is None:
            raise MatchActionError("Both match participants must be assigned before leasing")

        if lease is None:
            lease = ActiveLease(
                token=uuid4(),
                judge_id=TEMPORARY_JUDGE_ID,
                expires_at=timezone.now() + timedelta(seconds=MATCH_LEASE_SECONDS),
            )

        if match.status in (Match.Status.SCHEDULED, Match.Status.LINEUPS_OPEN):
            match.status = Match.Status.LIVE
            match.started_at = match.started_at or timezone.now()
            match.home_score = match.home_score if match.home_score is not None else 0
            match.away_score = match.away_score if match.away_score is not None else 0
            match.save(
                update_fields=["status", "started_at", "home_score", "away_score"]
            )
        elif match.status == Match.Status.LIVE and match.home_score is None:
            match.home_score = 0
            match.away_score = 0
            match.save(update_fields=["home_score", "away_score"])

        _renew_lease(match_id, lease)
        return {
            "match_id": match.id,
            "lease_token": lease.token,
            "expires_at": lease.expires_at,
            "expires_in_seconds": MATCH_LEASE_SECONDS,
        }


def renew_match_lease(match_id: int, lease_token: UUID) -> dict[str, Any]:
    """Extends the active judge lease without changing its token."""
    with _lease_lock:
        lease = _require_lease(match_id, lease_token)
        _renew_lease(match_id, lease)
        return {
            "match_id": match_id,
            "lease_token": lease.token,
            "expires_at": lease.expires_at,
            "expires_in_seconds": MATCH_LEASE_SECONDS,
        }


def release_match_lease(match_id: int, lease_token: UUID) -> dict[str, Any]:
    """Releases the active lease while leaving the match protocol intact."""
    with _lease_lock:
        _require_lease(match_id, lease_token)
        _active_leases.pop(match_id, None)
        return {"match_id": match_id, "released": True}


def takeover_match_lease(match_id: int) -> dict[str, Any]:
    """Rotates a live match lease token, invalidating the previous holder."""
    with _lease_lock, transaction.atomic():
        match = _get_match_for_update(match_id)
        if match.status != Match.Status.LIVE:
            raise MatchActionError("Only a live match can be taken over")
        lease = ActiveLease(
            token=uuid4(),
            judge_id=TEMPORARY_JUDGE_ID,
            expires_at=timezone.now() + timedelta(seconds=MATCH_LEASE_SECONDS),
        )
        _renew_lease(match_id, lease)
        return {
            "match_id": match_id,
            "lease_token": lease.token,
            "expires_at": lease.expires_at,
            "expires_in_seconds": MATCH_LEASE_SECONDS,
        }


def temporary_judge_match_ids() -> set[int]:
    """Возвращает матчи, занятые временным judge-ID, очищая истёкшие lease."""
    with _lease_lock:
        for match_id in list(_active_leases):
            _lease_for_match(match_id)
        return {
            match_id
            for match_id, lease in _active_leases.items()
            if lease.judge_id == TEMPORARY_JUDGE_ID
        }


def _validate_event(match: Match, event_data: dict[str, Any]) -> MatchEvent | None:
    """Проверяет участников, игрока и целевое событие протокола."""
    entry_id = event_data["entry_id"]
    player_id = event_data["entry_player_id"]
    related_player_id = event_data["related_entry_player_id"]
    target_event_id = event_data["target_event_id"]
    event_type = event_data["type"]
    participant_ids = {match.home_entry_id, match.away_entry_id} - {None}

    if entry_id is not None and entry_id not in participant_ids:
        raise MatchActionError("Event entry must be one of the match participants", 422)
    if event_type in (MatchEvent.Type.GOAL, MatchEvent.Type.OWN_GOAL) and entry_id is None:
        raise MatchActionError("Goal events require entry_id", 422)
    if player_id is not None:
        if entry_id is None or not EntryPlayer.objects.filter(pk=player_id, entry_id=entry_id).exists():
            raise MatchActionError("entry_player_id must belong to entry_id", 422)
    if related_player_id is not None:
        if entry_id is None or not EntryPlayer.objects.filter(
            pk=related_player_id, entry_id=entry_id
        ).exists():
            raise MatchActionError("related_entry_player_id must belong to entry_id", 422)
    if event_type == MatchEvent.Type.SUBSTITUTION:
        if player_id is None or related_player_id is None:
            raise MatchActionError("Substitution events require both player IDs", 422)
        if player_id == related_player_id:
            raise MatchActionError("A substitution requires two different players", 422)
    elif related_player_id is not None:
        raise MatchActionError("related_entry_player_id is only valid for substitution", 422)

    if event_type in (MatchEvent.Type.VOID, MatchEvent.Type.REVIEW_OK):
        if target_event_id is None:
            raise MatchActionError("Revision events require target_event_id", 422)
        target = MatchEvent.objects.filter(pk=target_event_id, match=match).first()
        if target is None or target.type in (MatchEvent.Type.VOID, MatchEvent.Type.REVIEW_OK):
            raise MatchActionError("target_event_id must reference a base event in this match", 422)
        return target
    if target_event_id is not None:
        raise MatchActionError("target_event_id is only valid for revision events", 422)
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


def append_match_event(match_id: int, event_data: dict[str, Any]) -> tuple[dict[str, Any], bool]:
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
    with _lease_lock:
        lease = _require_lease(match_id, lease_token)
        with transaction.atomic():
            match = _get_match_for_update(match_id)
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
                    raise MatchActionError("Device sequence or event ID already exists with different data")
                _renew_lease(match_id, lease)
                return _event_append_result(existing, match), False

            if match.status != Match.Status.LIVE:
                raise MatchActionError("Events can only be added to a live match")
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
        _renew_lease(match_id, lease)
        event.voided = False
        return _event_append_result(event, match), True


def _event_append_result(event: MatchEvent, match: Match) -> dict[str, Any]:
    """Builds the stable append response envelope from persisted match state."""
    match.refresh_from_db(fields=["home_score", "away_score"])
    last_seq = MatchEvent.objects.filter(match_id=match.id).aggregate(value=Max("seq"))["value"] or 0
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
    match_id: int, events_data: list[dict[str, Any]], lease_token: UUID
) -> tuple[dict[str, Any], bool]:
    """Appends a batch atomically and returns its event list and latest score."""
    results = []
    created_any = False
    with _lease_lock, transaction.atomic():
        _require_lease(match_id, lease_token)
        for item in events_data:
            result, created = append_match_event(
                match_id, {**item, "lease_token": lease_token}
            )
            results.append(result["event"])
            created_any = created_any or created
        match = _get_match_for_update(match_id)
        latest = _event_append_result(results[-1], match) if results else {
            "home_score": match.home_score,
            "away_score": match.away_score,
            "last_seq": MatchEvent.objects.filter(match=match).aggregate(value=Max("seq"))["value"] or 0,
        }
        return {
            "items": results,
            "home_score": latest["home_score"],
            "away_score": latest["away_score"],
            "last_seq": latest["last_seq"],
        }, created_any


def confirm_match(match_id: int, lease_token: UUID) -> Match:
    """Подтверждает завершённый матч при действующем lease-token."""
    with _lease_lock:
        lease = _require_lease(match_id, lease_token)
        with transaction.atomic():
            match = _get_match_for_update(match_id)
            if match.status == Match.Status.CONFIRMED:
                _renew_lease(match_id, lease)
                return match
            if match.status != Match.Status.FINISHED:
                raise MatchActionError("Only a finished match can be confirmed")
            match.status = Match.Status.CONFIRMED
            match.confirmed_at = timezone.now()
            match.save(update_fields=["status", "confirmed_at"])
        _renew_lease(match_id, lease)
        return match
