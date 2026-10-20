from datetime import date, datetime
from typing import Any, Literal

from ninja import Schema
from pydantic import Field


TournamentStatus = Literal["draft", "registration", "ongoing", "finished"]
TournamentVisibility = Literal["public", "unlisted", "private"]
StageKind = Literal["league", "groups", "playoff"]
TournamentEntryStatus = Literal["pending", "accepted", "rejected", "withdrawn"]


class OrganizationSummary(Schema):
    id: int
    name: str
    slug: str
    timezone: str


class TournamentStageSummary(Schema):
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


class GroupSummary(Schema):
    id: int
    name: str
    ord: int


class RoundSummary(Schema):
    id: int
    name: str
    ord: int


class TournamentOut(Schema):
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
    items: list[TournamentOut]
    total: int
    page: int
    page_size: int


class StandingRow(Schema):
    position: int
    entry_id: int
    team_id: int
    team_name: str
    played: int
    wins: int
    draws: int
    losses: int
    goals_for: int
    goals_against: int
    goal_difference: int
    points: int


class StageStandings(Schema):
    stage_id: int
    stage_name: str
    stage_kind: StageKind
    items: list[StandingRow]
    groups: list["GroupStandings"]


class GroupStandings(Schema):
    group_id: int
    group_name: str
    items: list[StandingRow]


class StandingsRules(Schema):
    points_for_win: int
    points_for_draw: int
    points_for_loss: int
    tie_breakers: list[str]


class StandingsOut(Schema):
    tournament_id: int
    stages: list[StageStandings]
    rules: StandingsRules


class OrganizerTournamentWriteIn(Schema):
    organization_id: int = Field(ge=1)
    slug: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    season: str = Field(default="", max_length=50)
    status: TournamentStatus = "draft"
    visibility: TournamentVisibility = "public"
    regulation: dict[str, Any] = Field(default_factory=dict)
    registration_deadline: datetime | None = None
    starts_on: date | None = None
    ends_on: date | None = None


class OrganizerTournamentPatchIn(Schema):
    slug: str | None = Field(default=None, min_length=1, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    season: str | None = Field(default=None, max_length=50)
    status: TournamentStatus | None = None
    visibility: TournamentVisibility | None = None
    regulation: dict[str, Any] | None = None
    registration_deadline: datetime | None = None
    starts_on: date | None = None
    ends_on: date | None = None


class OrganizerTournamentPatchIn(Schema):
    slug: str | None = Field(default=None, min_length=1, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    season: str | None = Field(default=None, max_length=50)
    status: TournamentStatus | None = None
    visibility: TournamentVisibility | None = None
    regulation: dict[str, Any] | None = None
    registration_deadline: datetime | None = None
    starts_on: date | None = None
    ends_on: date | None = None


class OrganizerTournamentOut(Schema):
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


class OrganizerTournamentListOut(Schema):
    items: list[OrganizerTournamentOut]
    total: int


class RegulationIn(Schema):
    regulation: dict[str, Any]


class OrganizerEntryOut(Schema):
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

class EntryTeamOut(Schema):
    id: int
    name: str
    city: str


class EntryCaptainOut(Schema):
    id: int
    name: str

    @staticmethod
    def resolve_name(user) -> str:
        return user.display_name or user.get_full_name() or user.username


class PublicParticipantsOut(Schema):
    items: list[EntryTeamOut]
    total: int


class OrganizerEntriesOut(Schema):
    items: list[OrganizerEntryOut]
    total: int


class StageWriteIn(Schema):
    ord: int = Field(ge=1, le=32767)
    kind: StageKind
    name: str = Field(min_length=1, max_length=100)


class StagePatchIn(Schema):
    ord: int | None = Field(default=None, ge=1, le=32767)
    kind: StageKind | None = None
    name: str | None = Field(default=None, min_length=1, max_length=100)


class OrganizerStageOut(Schema):
    id: int
    tournament_id: int
    ord: int
    kind: StageKind
    name: str


class OrganizerStagesOut(Schema):
    items: list[OrganizerStageOut]
    total: int


class GroupWriteIn(Schema):
    ord: int = Field(ge=1, le=32767)
    name: str = Field(min_length=1, max_length=100)


class GroupPatchIn(Schema):
    ord: int | None = Field(default=None, ge=1, le=32767)
    name: str | None = Field(default=None, min_length=1, max_length=100)


class OrganizerGroupOut(Schema):
    id: int
    stage_id: int
    ord: int
    name: str


class OrganizerGroupsOut(Schema):
    items: list[OrganizerGroupOut]
    total: int


class RoundWriteIn(Schema):
    ord: int = Field(ge=1, le=32767)
    name: str = Field(default="", max_length=100)


class RoundPatchIn(Schema):
    ord: int | None = Field(default=None, ge=1, le=32767)
    name: str | None = Field(default=None, max_length=100)


class OrganizerRoundOut(Schema):
    id: int
    stage_id: int
    ord: int
    name: str


class OrganizerRoundsOut(Schema):
    items: list[OrganizerRoundOut]
    total: int
