from datetime import date

from ninja import Schema
from pydantic import Field

from apps.teams.schemas.types import EntryPlayerStatus, TournamentEntryStatus


class CaptainTeamCreateIn(Schema):
    """Данные для создания команды капитаном."""

    name: str = Field(min_length=1, max_length=150)
    city: str = Field(default="", max_length=100)


class CaptainTeamPatchIn(Schema):
    """Частично изменяемые капитаном название и город команды."""

    name: str | None = Field(default=None, min_length=1, max_length=150)
    city: str | None = Field(default=None, max_length=100)


class CaptainTeamOut(Schema):
    """Краткий ответ после создания или изменения команды."""

    id: int
    name: str
    city: str


class CaptainTeamsOut(Schema):
    """Список команд капитана и их общее количество."""

    items: list[CaptainTeamOut]
    total: int


class EntryCreateIn(Schema):
    """Идентификатор команды для подачи заявки в турнир."""

    team_id: int = Field(ge=1)


class EntryTeamOut(Schema):
    """Краткие данные команды в ответе о заявке."""

    id: int
    name: str
    city: str


class CaptainEntryOut(Schema):
    """Результат подачи командной заявки на турнир."""

    id: int
    tournament_id: int
    team: EntryTeamOut
    status: TournamentEntryStatus


class EntryPlayerInput(Schema):
    """Существующий или новый игрок и его номер в заявке."""

    player_id: int | None = Field(default=None, ge=1)
    first_name: str | None = None
    last_name: str | None = None
    middle_name: str = ""
    birth_date: date | None = None
    number: int = Field(ge=1, le=99)


class EntryPlayersUpdateIn(Schema):
    """Полная замена списка игроков заявки."""

    players: list[EntryPlayerInput]


class EntryPlayerOut(Schema):
    """Игрок заявки с игровым номером и статусом участия."""

    entry_player_id: int
    player_id: int
    first_name: str
    last_name: str
    middle_name: str
    birth_date: date | None
    number: int
    status: EntryPlayerStatus


class EntryPlayersOut(Schema):
    """Сохранённый список игроков после изменения заявки."""

    entry_id: int
    players: list[EntryPlayerOut]


class EntryPlayersReadOut(Schema):
    """Список игроков, сохранённых в заявке."""

    entry_id: int
    players: list[EntryPlayerOut]
