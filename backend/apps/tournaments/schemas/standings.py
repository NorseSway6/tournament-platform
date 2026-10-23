from ninja import Schema

from .types import StageKind


class StandingRow(Schema):
    """Позиция команды в таблице результатов этапа или группы."""

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


class GroupStandings(Schema):
    """Таблица результатов отдельной группы."""

    group_id: int
    group_name: str
    items: list[StandingRow]


class StageStandings(Schema):
    """Таблица результатов этапа и его групп, если они есть."""

    stage_id: int
    stage_name: str
    stage_kind: StageKind
    items: list[StandingRow]
    groups: list["GroupStandings"]


class StandingsRules(Schema):
    """Очки и критерии сортировки таблиц турнира."""

    points_for_win: int
    points_for_draw: int
    points_for_loss: int
    tie_breakers: list[str]


class StandingsOut(Schema):
    """Таблицы всех этапов турнира вместе с применёнными правилами."""

    tournament_id: int
    stages: list[StageStandings]
    rules: StandingsRules
