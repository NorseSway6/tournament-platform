from datetime import date, datetime
from uuid import UUID

from ninja import Schema

from apps.matches.schemas.common import (
    EntrySummary,
    GroupSummary,
    MatchStageSummary,
    RoundSummary,
    TournamentSummary,
    VenueSummary,
)
from apps.matches.schemas.events import MatchEventOut
from apps.matches.schemas.types import MatchResultType, MatchStatus


class MatchOut(Schema):
    """Карточка матча с участниками, турниром, временем и счётом."""

    id: int
    tournament: TournamentSummary
    stage: MatchStageSummary
    round: RoundSummary | None
    group: GroupSummary | None
    home_entry: EntrySummary | None
    away_entry: EntrySummary | None
    venue: VenueSummary | None
    scheduled_at: datetime | None
    scheduled_end: datetime | None
    duration_min: int
    status: MatchStatus
    result_type: MatchResultType
    home_score: int | None
    away_score: int | None
    started_at: datetime | None
    finished_at: datetime | None
    confirmed_at: datetime | None


class MatchDetailOut(MatchOut):
    """Подробная карточка матча с лентой событий."""

    events: list[MatchEventOut]

    @staticmethod
    def resolve_events(match) -> list:
        """Возвращает ленту событий, предзагруженную selector-ом матча"""
        return match.public_events


class MatchPage(Schema):
    """Страница списка матчей с параметрами пагинации."""

    items: list[MatchOut]
    total: int
    page: int
    page_size: int


class TodayOut(Schema):
    """Матчи на выбранную дату для публичного раздела «Сегодня»."""

    date: date
    timezone: str | None
    items: list[MatchOut]
    total: int


class JudgeMatchesOut(Schema):
    """Матчи текущего судьи за выбранную дату."""

    date: date
    timezone: str | None
    items: list[MatchOut]
    total: int


class MatchLeaseOut(Schema):
    """Токен временной аренды матча и срок её действия."""

    match_id: int
    lease_token: UUID
    expires_at: datetime
    expires_in_seconds: int


class MatchLeaseActionIn(Schema):
    """Токен для операции с арендой матча."""

    lease_token: UUID


class MatchLeaseReleasedOut(Schema):
    """Результат освобождения аренды матча."""

    match_id: int
    released: bool


class MatchConfirmIn(Schema):
    """Данные для подтверждения завершённого матча."""

    lease_token: UUID


class MatchConfirmOut(Schema):
    """Подтверждённый счёт и статус матча."""

    id: int
    status: MatchStatus
    home_score: int
    away_score: int
    confirmed_at: datetime
