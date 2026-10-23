from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ninja import Schema
from pydantic import Field, field_validator


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
        """Rejects invalid time zones before calling the domain service."""
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
        """Rejects invalid time zones while preserving omitted/null semantics."""
        return _validate_timezone(value) if value is not None else value
