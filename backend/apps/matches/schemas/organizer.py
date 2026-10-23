from datetime import datetime

from ninja import Schema
from pydantic import Field

from apps.matches.schemas.types import MatchStatus, OfficialRole, StageKind


class VenueWriteIn(Schema):
    """Поля для создания площадки."""

    name: str = Field(min_length=1, max_length=150)
    address: str = Field(default="", max_length=300)
    notes: str = ""


class VenuePatchIn(Schema):
    """Частично изменяемые поля площадки."""

    name: str | None = Field(default=None, min_length=1, max_length=150)
    address: str | None = Field(default=None, max_length=300)
    notes: str | None = None


class VenueOut(Schema):
    """Полное представление площадки в API."""

    id: int
    name: str
    address: str
    notes: str


class VenueListOut(Schema):
    """Список площадок организации и его размер."""

    items: list[VenueOut]
    total: int


class AvailableJudgeOut(Schema):
    """Краткое представление доступного судьи."""

    id: int
    name: str


class AvailableJudgesOut(Schema):
    """Список доступных судей и его размер."""

    items: list[AvailableJudgeOut]
    total: int


class OrganizerMatchCreateIn(Schema):
    """Поля создания матча организатором в этапе турнира."""

    stage_id: int = Field(ge=1)
    round_id: int | None = Field(default=None, ge=1)
    group_id: int | None = Field(default=None, ge=1)
    home_entry_id: int = Field(ge=1)
    away_entry_id: int = Field(ge=1)
    venue_id: int | None = Field(default=None, ge=1)
    scheduled_at: datetime
    duration_min: int = Field(default=60, ge=1, le=32767)


class MatchSchedulePatchIn(Schema):
    """Новые дата и площадка при переносе матча."""

    scheduled_at: datetime
    venue_id: int | None = Field(default=None, ge=1)


class MatchOfficialIn(Schema):
    """Назначение одного официального лица на матч."""

    official_id: int = Field(ge=1)
    role: OfficialRole


class MatchOfficialsIn(Schema):
    """Полный список официальных лиц для замены назначений матча."""

    officials: list[MatchOfficialIn]


class MatchOfficialOut(Schema):
    """Назначенное официальное лицо и его функция на матче."""

    official_id: int
    name: str
    role: OfficialRole


class MatchOfficialsOut(Schema):
    """Назначения официальных лиц для указанного матча."""

    match_id: int
    officials: list[MatchOfficialOut]


class OrganizerMatchOut(Schema):
    """Представление матча в организаторских операциях."""

    id: int
    tournament_id: int
    stage_id: int
    round_id: int | None
    group_id: int | None
    home_entry_id: int | None
    away_entry_id: int | None
    venue_id: int | None
    scheduled_at: datetime | None
    scheduled_end: datetime | None
    duration_min: int
    status: MatchStatus
    home_score: int | None
    away_score: int | None
