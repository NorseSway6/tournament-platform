from datetime import datetime
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ninja import Schema
from pydantic import Field, field_validator

OrganizationMemberRole = Literal["organizer", "referee"]


def _validate_timezone(value: str) -> str:
    """Validates IANA time zones at the API boundary for structured 422 errors."""
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise ValueError("Enter a valid IANA timezone name.") from error
    return value


class OrganizationOut(Schema):
    """Контролируемое публичное представление организации"""

    id: int
    slug: str
    name: str
    description: str
    city: str
    timezone: str
    contacts: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class OrganizationListOut(Schema):
    """Ответ со списком организаций"""

    items: list[OrganizationOut]
    total: int


class OrganizationMemberAddIn(Schema):
    """Добавление участника организации по username или email."""

    identifier: str = Field(min_length=1, max_length=254)
    role: OrganizationMemberRole = "organizer"


class OrganizationMemberOut(Schema):
    """Участник организации и его роль в ней."""

    id: int
    user_id: int
    username: str
    display_name: str
    email: str | None
    role: OrganizationMemberRole
    created_at: datetime

    @staticmethod
    def resolve_user_id(member) -> int:
        """Возвращает идентификатор пользователя из членства."""
        return member.user_id

    @staticmethod
    def resolve_username(member) -> str:
        """Возвращает username участника."""
        return member.user.username

    @staticmethod
    def resolve_display_name(member) -> str:
        """Возвращает отображаемое имя участника."""
        user = member.user
        return user.display_name or user.get_full_name() or user.username

    @staticmethod
    def resolve_email(member) -> str | None:
        """Возвращает email участника."""
        return member.user.email


class OrganizationMemberListOut(Schema):
    """Список участников организации."""

    items: list[OrganizationMemberOut]
    total: int


class OrganizationCreateIn(Schema):
    """Поля создания организации"""

    slug: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    city: str = Field(default="", max_length=100)
    timezone: str = Field(default="UTC", min_length=1, max_length=64)
    contacts: dict[str, Any] = Field(default_factory=dict)

    @field_validator("timezone")
    @classmethod
    def timezone_must_be_valid(cls, value: str) -> str:
        """Отклоняет недопустимые часовые пояса перед вызовом доменного сервиса."""
        return _validate_timezone(value)


class OrganizationPatchIn(Schema):
    """Частично изменяемые поля организации"""

    slug: str | None = Field(default=None, min_length=1, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    city: str | None = Field(default=None, max_length=100)
    timezone: str | None = Field(default=None, min_length=1, max_length=64)
    contacts: dict[str, Any] | None = None

    @field_validator("timezone")
    @classmethod
    def timezone_must_be_valid(cls, value: str | None) -> str | None:
        """Отклоняет некорректные часовые пояса, сохраняя при этом семантику для пропущенных или null-значений."""
        return _validate_timezone(value) if value is not None else value
