from datetime import date, datetime
from typing import Literal
from uuid import UUID

from ninja import Schema
from pydantic import Field


MatchStatus = Literal[
    "scheduled", "lineups_open", "live", "finished", "confirmed",
    "postponed", "cancelled", "technical",
]
MatchResultType = Literal["played", "tech_win_home", "tech_win_away", "walkover"]
MatchEventType = Literal[
    "goal", "own_goal", "yellow", "red", "sub", "period_start",
    "period_end", "pause", "resume", "finish", "void", "review_ok", "note",
]
LineupStatus = Literal["draft", "submitted", "accepted", "rejected"]
LineupPlayerRole = Literal["player", "captain"]
OfficialRole = Literal["referee", "assistant_referee", "fourth_official", "delegate"]
StageKind = Literal["league", "groups", "playoff"]
EntryStatus = Literal["pending", "accepted", "rejected", "withdrawn"]
EventPeriod = Literal[
    "first_half", "half_time", "second_half", "extra_time_first",
    "extra_time_second", "penalties",
]
EventSource = Literal["judge", "organizer", "system"]


class TeamSummary(Schema):
    id: int
    name: str
    city: str


class EntrySummary(Schema):
    id: int
    status: EntryStatus
    team: TeamSummary


class TournamentSummary(Schema):
    id: int
    slug: str
    name: str
    timezone: str

    @staticmethod
    def resolve_timezone(tournament) -> str:
        """Returns the timezone configured for the tournament's organization."""
        return tournament.organization.timezone


class MatchStageSummary(Schema):
    id: int
    name: str
    kind: StageKind
    ord: int


class RoundSummary(Schema):
    id: int
    name: str
    ord: int


class GroupSummary(Schema):
    id: int
    name: str
    ord: int


class VenueSummary(Schema):
    id: int
    name: str
    address: str


class VenueWriteIn(Schema):
    name: str = Field(min_length=1, max_length=150)
    address: str = Field(default="", max_length=300)
    notes: str = ""


class VenuePatchIn(Schema):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    address: str | None = Field(default=None, max_length=300)
    notes: str | None = None


class VenueOut(Schema):
    id: int
    name: str
    address: str
    notes: str


class VenueListOut(Schema):
    items: list[VenueOut]
    total: int


class AvailableJudgeOut(Schema):
    id: int
    name: str


class AvailableJudgesOut(Schema):
    items: list[AvailableJudgeOut]
    total: int


class EventPlayerSummary(Schema):
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
            part
            for part in (player.last_name, player.first_name, player.middle_name)
            if part
        )


class MatchEventOut(Schema):
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


class MatchOut(Schema):
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
    events: list[MatchEventOut]

    @staticmethod
    def resolve_events(match) -> list:
        """Возвращает ленту событий, предзагруженную selector-ом матча"""
        return match.public_events


class MatchPage(Schema):
    items: list[MatchOut]
    total: int
    page: int
    page_size: int


class TodayOut(Schema):
    date: date
    items: list[MatchOut]
    total: int


class JudgeMatchesOut(Schema):
    date: date
    items: list[MatchOut]
    total: int


class MatchLeaseOut(Schema):
    match_id: int
    lease_token: UUID
    expires_at: datetime
    expires_in_seconds: int


class MatchLeaseActionIn(Schema):
    lease_token: UUID


class MatchLeaseReleasedOut(Schema):
    match_id: int
    released: bool


class MatchEventFields(Schema):
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
    lease_token: UUID


class MatchEventsBatchIn(Schema):
    lease_token: UUID
    events: list[MatchEventFields] = Field(min_length=1, max_length=100)


class MatchEventAppendOut(Schema):
    event: MatchEventOut
    home_score: int | None
    away_score: int | None
    last_seq: int


class MatchEventsBatchOut(Schema):
    items: list[MatchEventOut]
    home_score: int | None
    away_score: int | None
    last_seq: int


class MatchEventFeedOut(Schema):
    match_id: int
    after_seq: int
    last_seq: int
    items: list[MatchEventOut]


class MatchConfirmIn(Schema):
    lease_token: UUID


class MatchConfirmOut(Schema):
    id: int
    status: MatchStatus
    home_score: int
    away_score: int
    confirmed_at: datetime


class LineupPlayerIn(Schema):
    entry_player_id: int = Field(ge=1)
    is_starter: bool = False
    role: LineupPlayerRole = "player"


class LineupUpdateIn(Schema):
    players: list[LineupPlayerIn]


class LineupPlayerOut(Schema):
    entry_player_id: int
    player_id: int
    first_name: str
    last_name: str
    middle_name: str
    number: int
    is_starter: bool
    role: LineupPlayerRole
    selected: bool


class MatchLineupOut(Schema):
    match_id: int
    entry_id: int
    lineup_id: int | None
    status: LineupStatus
    players: list[LineupPlayerOut]


class JudgeLineupPlayerOut(Schema):
    entry_player_id: int
    player_id: int
    name: str
    number: int
    is_starter: bool
    role: LineupPlayerRole


class JudgeLineupOut(Schema):
    entry_id: int
    team_id: int
    team_name: str
    lineup_id: int | None
    status: LineupStatus | None
    reject_reason: str
    players: list[JudgeLineupPlayerOut]


class JudgeLineupsOut(Schema):
    match_id: int
    items: list[JudgeLineupOut]


class MatchLineupDecisionIn(Schema):
    status: Literal["accepted", "rejected"]
    reject_reason: str = ""


class MatchLineupDecisionOut(Schema):
    id: int
    match_id: int
    entry_id: int
    status: Literal["accepted", "rejected"]
    reject_reason: str


class LineupCheckOut(Schema):
    lineup_id: int
    match_id: int
    entry_id: int
    status: LineupStatus
    valid: bool
    issues: list[str]
    player_count: int
    starters_count: int
    captains_count: int


class OrganizerMatchCreateIn(Schema):
    stage_id: int = Field(ge=1)
    round_id: int | None = Field(default=None, ge=1)
    group_id: int | None = Field(default=None, ge=1)
    home_entry_id: int = Field(ge=1)
    away_entry_id: int = Field(ge=1)
    venue_id: int | None = Field(default=None, ge=1)
    scheduled_at: datetime
    duration_min: int = Field(default=60, ge=1, le=32767)


class MatchSchedulePatchIn(Schema):
    scheduled_at: datetime
    venue_id: int | None = Field(default=None, ge=1)


class MatchOfficialIn(Schema):
    official_id: int = Field(ge=1)
    role: OfficialRole


class MatchOfficialsIn(Schema):
    officials: list[MatchOfficialIn]


class MatchOfficialOut(Schema):
    official_id: int
    name: str
    role: OfficialRole


class MatchOfficialsOut(Schema):
    match_id: int
    officials: list[MatchOfficialOut]


class OrganizerMatchOut(Schema):
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


class ProtocolEventReplacementIn(Schema):
    type: Literal[
        "goal", "own_goal", "yellow", "red", "sub", "period_start",
        "period_end", "pause", "resume", "finish", "note",
    ]
    entry_id: int | None = Field(default=None, ge=1)
    entry_player_id: int | None = Field(default=None, ge=1)
    related_entry_player_id: int | None = Field(default=None, ge=1)
    period: EventPeriod | None = None
    clock_ms: int | None = Field(default=None, ge=0, le=7_200_000)
    minute: int | None = Field(default=None, ge=0)
    second: int | None = Field(default=None, ge=0, le=59)


class ProtocolCorrectionIn(Schema):
    target_event_id: UUID
    reason: str = Field(min_length=1, max_length=2000)
    action: Literal["void", "replace"]
    replacement: ProtocolEventReplacementIn | None = None


class ProtocolCorrectionOut(Schema):
    match_id: int
    voided_event_id: str
    replacement_event: MatchEventOut | None
    home_score: int
    away_score: int
    status: MatchStatus
    reason: str
