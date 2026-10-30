from datetime import datetime
from typing import Literal
from uuid import UUID

from ninja import Schema
from pydantic import Field

from apps.matches.schemas.types import (
    EventPeriod,
    EventSource,
    MatchEventType,
    MatchStatus,
)


class EventPlayerSummary(Schema):
    """Игрок и его запись в заявке для события матча."""

    entry_player_id: int
    player_id: int
    name: str
    number: int

    @staticmethod
    def resolve_entry_player_id(entry_player) -> int:
        """Отдаёт ID записи игрока в составе заявки на турнир"""
        return entry_player.id

    @staticmethod
    def resolve_name(entry_player) -> str:
        """Собирает публичное имя игрока, связанного с событием"""
        player = entry_player.player
        return " ".join(
            part for part in (player.last_name, player.first_name, player.middle_name) if part
        )


class MatchEventOut(Schema):
    """Событие протокола матча, включая состояние отмены."""

    id: str
    seq: int
    device_id: UUID | None
    client_seq: int | None
    type: MatchEventType
    entry_id: int | None
    player: EventPlayerSummary | None
    related_entry_player_id: int | None
    period: EventPeriod | None
    clock_ms: int | None
    minute: int | None
    second: int | None
    client_created_at: datetime | None
    created_at: datetime
    target_event_id: str | None
    needs_review: bool
    source: EventSource
    voided: bool

    @staticmethod
    def resolve_id(event) -> str:
        """Сериализует UUID события в строковый формат API"""
        return str(event.id)

    @staticmethod
    def resolve_target_event_id(event) -> str | None:
        """Сериализует UUID отменяемого или пересматриваемого события"""
        return str(event.target_event_id) if event.target_event_id else None

    @staticmethod
    def resolve_voided(event) -> bool:
        """Reports whether an append-only correction voided this event."""
        return bool(getattr(event, "voided", False))

    @staticmethod
    def resolve_related_entry_player_id(event) -> int | None:
        """Serializes the second player in a substitution, if present."""
        return event.related_player_id


class MatchEventFields(Schema):
    """Общие поля события для одиночной и пакетной отправки."""

    id: UUID
    device_id: UUID
    client_seq: int = Field(ge=1)
    type: MatchEventType
    entry_id: int | None = Field(default=None, ge=1)
    entry_player_id: int | None = Field(default=None, ge=1)
    related_entry_player_id: int | None = Field(default=None, ge=1)
    period: EventPeriod | None = None
    clock_ms: int | None = Field(default=None, ge=0, le=7_200_000)
    minute: int | None = Field(default=None, ge=0)
    second: int | None = Field(default=None, ge=0, le=59)
    client_created_at: datetime | None = None
    target_event_id: UUID | None = None
    needs_review: bool = False


class MatchEventCreate(MatchEventFields):
    """Новое событие протокола вместе с токеном аренды."""

    lease_token: UUID


class MatchEventsBatchIn(Schema):
    """Пакет событий, отправляемых под одной арендой."""

    lease_token: UUID
    events: list[MatchEventFields] = Field(min_length=1, max_length=100)


class MatchEventAppendOut(Schema):
    """Созданное событие и счёт матча после его обработки."""

    event: MatchEventOut
    home_score: int | None
    away_score: int | None
    last_seq: int


class MatchEventsBatchOut(Schema):
    """Результат пакетной отправки и актуальный счёт матча."""

    items: list[MatchEventOut]
    home_score: int | None
    away_score: int | None
    last_seq: int


class MatchEventFeedOut(Schema):
    """Лента событий матча после указанного sequence-номера."""

    match_id: int
    after_seq: int
    last_seq: int
    items: list[MatchEventOut]


class ProtocolEventReplacementIn(Schema):
    """Поля нового события для замены при исправлении протокола."""

    type: Literal[
        "goal",
        "own_goal",
        "yellow",
        "red",
        "sub",
        "period_start",
        "period_end",
        "pause",
        "resume",
        "finish",
        "note",
    ]
    entry_id: int | None = Field(default=None, ge=1)
    entry_player_id: int | None = Field(default=None, ge=1)
    related_entry_player_id: int | None = Field(default=None, ge=1)
    period: EventPeriod | None = None
    clock_ms: int | None = Field(default=None, ge=0, le=7_200_000)
    minute: int | None = Field(default=None, ge=0)
    second: int | None = Field(default=None, ge=0, le=59)


class ProtocolCorrectionIn(Schema):
    """Причина и действие для аудируемого исправления события."""

    target_event_id: UUID
    reason: str = Field(min_length=1, max_length=2000)
    action: Literal["void", "replace"]
    replacement: ProtocolEventReplacementIn | None = None


class ProtocolCorrectionOut(Schema):
    """Результат исправления протокола и пересчитанный счёт."""

    match_id: int
    voided_event_id: str
    replacement_event: MatchEventOut | None
    home_score: int
    away_score: int
    status: MatchStatus
    reason: str
