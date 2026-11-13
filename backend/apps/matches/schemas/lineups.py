from typing import Literal

from ninja import Schema
from pydantic import Field

from apps.matches.schemas.types import LineupPlayerRole, LineupStatus


class LineupPlayerIn(Schema):
    """Игрок заявки, выбранный капитаном в состав матча."""

    entry_player_id: int = Field(ge=1)
    is_starter: bool = False
    role: LineupPlayerRole = "player"


class LineupUpdateIn(Schema):
    """Полный список игроков и комментарий для замены черновика состава."""

    players: list[LineupPlayerIn]
    comment: str = Field(default="", max_length=2000)


class LineupPlayerOut(Schema):
    """Игрок состава с номером, ролью и признаком выбора."""

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
    """Состав одной команды в матче для капитана."""

    match_id: int
    entry_id: int
    lineup_id: int | None
    status: LineupStatus
    comment: str
    players: list[LineupPlayerOut]


class JudgeLineupPlayerOut(Schema):
    """Публичные данные игрока в заявке на матч."""

    entry_player_id: int
    player_id: int
    name: str
    number: int
    is_starter: bool
    role: LineupPlayerRole


class JudgeLineupOut(Schema):
    """Заявка одной команды на матч для проверки судьёй."""

    entry_id: int
    team_id: int
    team_name: str
    lineup_id: int | None
    status: LineupStatus | None
    comment: str
    reject_reason: str
    players: list[JudgeLineupPlayerOut]


class JudgeLineupsOut(Schema):
    """Заявки обеих команд в рамках одного матча."""

    match_id: int
    items: list[JudgeLineupOut]


class MatchLineupDecisionIn(Schema):
    """Решение судьи о принятии или отклонении состава."""

    status: Literal["accepted", "rejected"]
    reject_reason: str = ""


class MatchLineupDecisionOut(Schema):
    """Сохранённое решение по составу команды."""

    id: int
    match_id: int
    entry_id: int
    status: Literal["accepted", "rejected"]
    reject_reason: str


class LineupCheckOut(Schema):
    """Результат проверки состава и список найденных проблем."""

    lineup_id: int
    match_id: int
    entry_id: int
    status: LineupStatus
    valid: bool
    issues: list[str]
    player_count: int
    starters_count: int
    captains_count: int
