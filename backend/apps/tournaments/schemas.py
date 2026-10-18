from datetime import date, datetime

from ninja import Schema


class OrganizationSummary(Schema):
    id: int
    name: str
    slug: str


class StageSummary(Schema):
    id: int
    name: str
    kind: str
    ord: int


class TournamentOut(Schema):
    id: int
    organization: OrganizationSummary
    slug: str
    name: str
    season: str
    status: str
    visibility: str
    registration_deadline: datetime | None
    starts_on: date | None
    ends_on: date | None
    stages: list[StageSummary]


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
    stage_kind: str
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
