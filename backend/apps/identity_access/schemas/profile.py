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
        "scheduled",
        "lineups_open",
        "live",
        "finished",
        "confirmed",
        "postponed",
        "cancelled",
        "technical",
    ]
    scheduled_at: datetime | None


class MeCaptainRoleOut(Schema):
    """Доступная капитану область команд."""

    enabled: bool
    teams: list[MeTeamContextOut]


class MeOrganizerRoleOut(Schema):
    """Доступная организатору область организаций и турниров."""

    enabled: bool
    organizations: list[MeOrganizationContextOut]


class MeJudgeRoleOut(Schema):
    """Доступная судье область назначенных матчей."""

    enabled: bool
    matches: list[MeMatchContextOut]


class MeAdminRoleOut(Schema):
    """Глобальная административная роль платформы."""

    enabled: bool


class MeRolesOut(Schema):
    """Набор ролевых областей профиля."""

    captain: MeCaptainRoleOut
    organizer: MeOrganizerRoleOut
    judge: MeJudgeRoleOut
    admin: MeAdminRoleOut


class MeOut(Schema):
    """Профиль и ролевые области пользователя access-токена."""

    authenticated: bool
    profile: MeProfileOut | None
    roles: MeRolesOut
