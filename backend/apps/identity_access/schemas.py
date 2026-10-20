from datetime import datetime
from typing import Literal

from ninja import Schema


class MeProfileOut(Schema):
    """Публичные поля профиля для интерфейса пользователя."""

    id: int
    username: str
    display_name: str
    first_name: str
    last_name: str


class MeEntryContextOut(Schema):
    """Заявка команды капитана на участие в турнире."""

    id: int
    tournament_id: int
    tournament_name: str
    status: Literal["pending", "accepted", "rejected", "withdrawn"]


class MeTeamContextOut(Schema):
    """Команда и заявки, доступные капитану."""

    id: int
    name: str
    city: str
    entries: list[MeEntryContextOut]


class MeTournamentContextOut(Schema):
    """Турнир в области управления организатора."""

    id: int
    slug: str
    name: str
    status: Literal["draft", "registration", "ongoing", "finished"]


class MeOrganizationContextOut(Schema):
    """Организация и её турниры, доступные организатору."""

    id: int
    slug: str
    name: str
    city: str
    timezone: str
    tournaments: list[MeTournamentContextOut]


class MeMatchContextOut(Schema):
    """Матч, назначенный судье."""

    id: int
    tournament_id: int
    tournament_name: str
    status: Literal[
        "scheduled", "lineups_open", "live", "finished", "confirmed",
        "postponed", "cancelled", "technical",
    ]
    scheduled_at: datetime | None


class MeCaptainRoleOut(Schema):
    enabled: bool
    teams: list[MeTeamContextOut]


class MeOrganizerRoleOut(Schema):
    enabled: bool
    organizations: list[MeOrganizationContextOut]


class MeJudgeRoleOut(Schema):
    enabled: bool
    matches: list[MeMatchContextOut]


class MeRolesOut(Schema):
    captain: MeCaptainRoleOut
    organizer: MeOrganizerRoleOut
    judge: MeJudgeRoleOut


class MeOut(Schema):
    """Профиль и ролевые области текущего временного пользователя."""

    identity_mode: Literal["temporary"]
    authenticated: bool
    profile: MeProfileOut | None
    roles: MeRolesOut
