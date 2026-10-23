from datetime import datetime
from typing import Literal

from ninja import Schema
from pydantic import Field


class AuthRegisterIn(Schema):
    """Данные регистрации новой учетной записи."""

    username: str = Field(min_length=1, max_length=150)
    password: str = Field(min_length=8, max_length=128)
    email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=16)
    telegram_id: int | None = None
    telegram_username: str = Field(default="", max_length=64)
    display_name: str = Field(default="", max_length=150)
    first_name: str = Field(default="", max_length=150)
    last_name: str = Field(default="", max_length=150)


class UserOut(Schema):
    """Безопасное представление пользователя после регистрации или входа."""

    id: int
    username: str
    email: str | None
    phone: str | None
    display_name: str


class AuthLoginIn(Schema):
    """Идентификатор и пароль для входа."""

    identifier: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class RefreshTokenIn(Schema):
    """Refresh-токен для ротации или завершения сессии."""

    refresh_token: str = Field(min_length=20, max_length=256)


class AuthTokenPairOut(Schema):
    """Пара токенов и профиль пользователя после регистрации или входа."""

    access_token: str
    refresh_token: str
    token_type: Literal["Bearer"]
    expires_in: int
    refresh_expires_at: datetime
    user: UserOut
