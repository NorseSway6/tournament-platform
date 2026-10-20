from datetime import date
from typing import Literal

from ninja import Schema
from pydantic import Field


class PersonSummary(Schema):
    id: int
    name: str


TournamentStatus = Literal["draft", "registration", "ongoing", "finished"]
TournamentEntryStatus = Literal["pending", "accepted", "rejected", "withdrawn"]
EntryPlayerStatus = Literal["active", "removed"]


class CaptainSummary(Schema):
    id: int
    name: str

    @staticmethod
    def resolve_name(user) -> str:
        """Извлекает публичное отображаемое имя капитана."""
        return user.display_name or user.get_full_name() or user.username


class TournamentMembership(Schema):
    id: int
    slug: str
    name: str
    status: TournamentStatus


class TeamTournamentMembership(TournamentMembership):
    entry_status: TournamentEntryStatus

    @staticmethod
    def resolve_id(entry) -> int:
        """Берёт ID турнира из заявки команды."""
        return entry.tournament_id

    @staticmethod
    def resolve_slug(entry) -> str:
        """Берёт slug турнира из заявки команды."""
        return entry.tournament.slug

    @staticmethod
    def resolve_name(entry) -> str:
        """Берёт название турнира из заявки команды."""
        return entry.tournament.name

    @staticmethod
    def resolve_status(entry) -> str:
        """Возвращает статус турнира, не подменяя его статусом заявки."""
        return entry.tournament.status

    @staticmethod
    def resolve_entry_status(entry) -> str:
        """Возвращает статус заявки команды на турнир."""
        return entry.status


class TeamOut(Schema):
    id: int
    name: str
    city: str
    captain: CaptainSummary
    tournaments: list[TeamTournamentMembership]

    @staticmethod
    def resolve_tournaments(team) -> list:
        """Использует отфильтрованные публичные заявки из selector."""
        return team.public_entries


class CaptainTeamCreateIn(Schema):
    name: str = Field(min_length=1, max_length=150)
    city: str = Field(default="", max_length=100)


class CaptainTeamPatchIn(Schema):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    city: str | None = Field(default=None, max_length=100)


class CaptainTeamOut(Schema):
    id: int
    name: str
    city: str


class CaptainTeamsOut(Schema):
    items: list[CaptainTeamOut]
    total: int


class PlayerEntryOut(Schema):
    entry_id: int
    number: int
    status: EntryPlayerStatus
    team: PersonSummary
    tournament: TournamentMembership

    @staticmethod
    def resolve_team(membership):
        """Возвращает команду, связанную с заявкой игрока."""
        return membership.entry.team

    @staticmethod
    def resolve_tournament(membership):
        """Возвращает турнир, связанный с заявкой игрока."""
        return membership.entry.tournament


class PlayerOut(Schema):
    id: int
    first_name: str
    last_name: str
    middle_name: str
    full_name: str
    entries: list[PlayerEntryOut]

    @staticmethod
    def resolve_full_name(player) -> str:
        """Собирает полное имя из публичных полей профиля игрока."""
        return " ".join(
            part
            for part in (player.last_name, player.first_name, player.middle_name)
            if part
        )

    @staticmethod
    def resolve_entries(player) -> list:
        """Возвращает только публичные активные составы игрока."""
        return player.public_memberships


class EntryCreateIn(Schema):
    team_id: int = Field(ge=1)


class EntryTeamOut(Schema):
    id: int
    name: str
    city: str


class CaptainEntryOut(Schema):
    id: int
    tournament_id: int
    team: EntryTeamOut
    status: TournamentEntryStatus


class EntryPlayerInput(Schema):
    player_id: int | None = Field(default=None, ge=1)
    first_name: str | None = None
    last_name: str | None = None
    middle_name: str = ""
    birth_date: date | None = None
    number: int = Field(ge=1, le=99)


class EntryPlayersUpdateIn(Schema):
    players: list[EntryPlayerInput]


class EntryPlayerOut(Schema):
    entry_player_id: int
    player_id: int
    first_name: str
    last_name: str
    middle_name: str
    birth_date: date | None
    number: int
    status: EntryPlayerStatus


class EntryPlayersOut(Schema):
    entry_id: int
    players: list[EntryPlayerOut]


class EntryPlayersReadOut(Schema):
    entry_id: int
    players: list[EntryPlayerOut]


class EntryDecisionIn(Schema):
    status: Literal["accepted", "rejected"]
    decision_comment: str = Field(default="", max_length=2000)


class EntryDecisionOut(Schema):
    id: int
    tournament_id: int
    team_id: int
    status: TournamentEntryStatus
    decision_comment: str
