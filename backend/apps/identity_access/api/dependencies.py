from collections.abc import Callable
from typing import Any

from django.http import HttpRequest
from ninja.errors import HttpError
from ninja.security import HttpBearer

from apps.identity_access.services import user_from_access_token


class AccessTokenAuth(HttpBearer):
    """Выполняет проверку bearer token с возможностью дополнительной проверки доменных прав доступа."""

    def __init__(
        self,
        permission_check: Callable[[HttpRequest, Any], bool] | None = None,
        forbidden_message: str = "Access to this resource is forbidden",
    ) -> None:
        self.permission_check = permission_check
        self.forbidden_message = forbidden_message
        super().__init__()

    def authenticate(self, request: HttpRequest, token: str):
        user = user_from_access_token(token)
        if user is None:
            return None
        if self.permission_check and not self.permission_check(request, user):
            raise HttpError(403, self.forbidden_message)
        return user


access_token_auth = AccessTokenAuth()


def request_user_id(request: HttpRequest) -> int:
    """Возвращает идентификатор аутентифицированного пользователя, полученный посредством bearer-аутентификации."""
    user = getattr(request, "auth", None)
    if user is None or not getattr(user, "is_authenticated", False):
        raise HttpError(401, "A valid Bearer access token is required")
    return user.pk
