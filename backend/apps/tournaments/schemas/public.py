from datetime import date, datetime

from ninja import Schema

from .common import EntryTeamOut, GroupSummary, OrganizationSummary, RoundSummary
from .types import StageKind, TournamentStatus, TournamentVisibility


class TournamentStageSummary(Schema):
    """Этап турнира с вложенными группами и турами."""

    id: int
    name: str
    kind: StageKind
    ord: int
    groups: list["GroupSummary"]
    rounds: list["RoundSummary"]

    @staticmethod
    def resolve_groups(stage):
        return list(stage.groups.all())

    @staticmethod
    def resolve_rounds(stage):
        return list(stage.rounds.all())


class TournamentOut(Schema):
    """Публичная карточка турнира с организацией и этапами."""

    id: int
    organization: OrganizationSummary
    slug: str
    name: str
    season: str
    status: TournamentStatus
    visibility: TournamentVisibility
    registration_deadline: datetime | None
    starts_on: date | None
    ends_on: date | None
    stages: list[TournamentStageSummary]


class TournamentListResponse(Schema):
    """Страница списка публичных турниров."""

    items: list[TournamentOut]
    total: int
    page: int
    page_size: int


class PublicParticipantsOut(Schema):
    """Принятые команды публичного турнира."""

    items: list[EntryTeamOut]
    total: int
