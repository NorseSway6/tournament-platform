from datetime import date, datetime
from typing import Any

from ninja import Schema
from pydantic import Field

from .common import EntryCaptainOut, EntryTeamOut
from .types import StageKind, TournamentEntryStatus, TournamentStatus, TournamentVisibility


class OrganizerEntryOut(Schema):
    """Заявка на турнир с командой, капитаном и числом игроков."""

    id: int
    tournament_id: int
    team_id: int
    team: "EntryTeamOut"
    captain: "EntryCaptainOut | None"
    submitted_at: datetime
    player_count: int
    decision_comment: str
    status: TournamentEntryStatus

    @staticmethod
    def resolve_team(entry):
        return entry.team

    @staticmethod
    def resolve_captain(entry):
        return entry.team.captain


class OrganizerTournamentOut(Schema):
    """Полное представление турнира для организаторских операций."""

    id: int
    organization_id: int
    slug: str
    name: str
    season: str
    status: TournamentStatus
    visibility: TournamentVisibility
    regulation: dict[str, Any]
    registration_deadline: datetime | None
    starts_on: date | None
    ends_on: date | None
    created_at: datetime
    updated_at: datetime


class OrganizerTournamentWriteIn(Schema):
    """Данные для создания турнира организатором."""

    organization_id: int = Field(ge=1)
    slug: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    season: str = Field(default="", max_length=50)
    visibility: TournamentVisibility = "public"
    regulation: dict[str, Any] = Field(default_factory=dict)
    registration_deadline: datetime | None = None
    starts_on: date | None = None
    ends_on: date | None = None


class OrganizerRoundOut(Schema):
    """Представление тура для организаторского API."""

    id: int
    stage_id: int
    ord: int
    name: str


class OrganizerGroupOut(Schema):
    """Представление группы для организаторского API."""

    id: int
    stage_id: int
    ord: int
    name: str


class OrganizerStageOut(Schema):
    """Представление этапа для организаторского API."""

    id: int
    tournament_id: int
    ord: int
    kind: StageKind
    name: str


class OrganizerEntriesOut(Schema):
    """Список заявок турнира для рассмотрения организатором."""

    items: list[OrganizerEntryOut]
    total: int


class OrganizerGroupEntryOut(Schema):
    """Принятая заявка, назначенная в группу этапа."""

    entry_id: int
    team_id: int
    team_name: str
    status: TournamentEntryStatus

    @staticmethod
    def resolve_team_id(item):
        return item.entry.team_id

    @staticmethod
    def resolve_team_name(item):
        return item.entry.team.name

    @staticmethod
    def resolve_status(item):
        return item.entry.status


class OrganizerGroupEntriesOut(Schema):
    """Список заявок, назначенных в группу."""

    items: list[OrganizerGroupEntryOut]
    total: int


class GroupEntriesReplaceIn(Schema):
    """Полный список заявок, которые должны быть назначены в группу."""

    entry_ids: list[int] = Field(default_factory=list)


class StagePatchIn(Schema):
    """Частично изменяемые поля этапа турнира."""

    ord: int | None = Field(default=None, ge=1, le=32767)
    kind: StageKind | None = None
    name: str | None = Field(default=None, min_length=1, max_length=100)


class GroupWriteIn(Schema):
    """Поля для создания группы в групповом этапе."""

    ord: int = Field(ge=1, le=32767)
    name: str = Field(min_length=1, max_length=100)


class RegulationIn(Schema):
    """Новый объект регламента для полной замены текущего."""

    regulation: dict[str, Any]


class StageWriteIn(Schema):
    """Поля для создания этапа турнира."""

    ord: int = Field(ge=1, le=32767)
    kind: StageKind
    name: str = Field(min_length=1, max_length=100)


class GroupPatchIn(Schema):
    """Частично изменяемые поля группы."""

    ord: int | None = Field(default=None, ge=1, le=32767)
    name: str | None = Field(default=None, min_length=1, max_length=100)


class RoundWriteIn(Schema):
    """Поля для создания тура этапа."""

    ord: int = Field(ge=1, le=32767)
    name: str = Field(default="", max_length=100)


class RoundPatchIn(Schema):
    """Частично изменяемые поля тура."""

    ord: int | None = Field(default=None, ge=1, le=32767)
    name: str | None = Field(default=None, max_length=100)


class OrganizerTournamentPatchIn(Schema):
    """Частично изменяемые поля существующего турнира."""

    slug: str | None = Field(default=None, min_length=1, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    season: str | None = Field(default=None, max_length=50)
    visibility: TournamentVisibility | None = None
    registration_deadline: datetime | None = None
    starts_on: date | None = None
    ends_on: date | None = None


class OrganizerTournamentListOut(Schema):
    """Список турниров выбранной организации."""

    items: list[OrganizerTournamentOut]
    total: int


class OrganizerStagesOut(Schema):
    """Список этапов турнира."""

    items: list[OrganizerStageOut]
    total: int


class OrganizerGroupsOut(Schema):
    """Список групп этапа."""

    items: list[OrganizerGroupOut]
    total: int


class OrganizerRoundsOut(Schema):
    """Список туров этапа."""

    items: list[OrganizerRoundOut]
    total: int
