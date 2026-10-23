from typing import Literal

from ninja import Schema
from pydantic import Field

from apps.teams.schemas.types import TournamentEntryStatus


class EntryDecisionIn(Schema):
    """Решение организатора по заявке и поясняющий комментарий."""

    status: Literal["accepted", "rejected"]
    decision_comment: str = Field(default="", max_length=2000)


class EntryDecisionOut(Schema):
    """Обновлённое состояние рассмотренной заявки."""

    id: int
    tournament_id: int
    team_id: int
    status: TournamentEntryStatus
    decision_comment: str
