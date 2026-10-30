from django.http import HttpRequest
from ninja import Router

from apps.common.api_errors import api_response
from apps.identity_access.api.dependencies import (
    access_token_auth,
    request_user_id,
)
from apps.identity_access.schemas.auth import (
    AuthLoginIn,
    AuthRegisterIn,
    AuthTokenPairOut,
    RefreshTokenIn,
)
from apps.identity_access.schemas.profile import MeOut
from apps.identity_access.services import (
    create_token_pair,
    create_user,
    login_user,
    refresh_token_pair,
    revoke_refresh_token,
)
from apps.role_assignment import get_me as get_user_context

router = Router(tags=["Identity"])


@router.post("/auth/register", response=api_response({201: AuthTokenPairOut}))
def register_user(request: HttpRequest, payload: AuthRegisterIn):
    """Создаёт обычную учетную запись и сразу выдаёт пару токенов."""
    user = create_user(payload.model_dump())
    tokens = create_token_pair(user)
    return 201, tokens


@router.post("/auth/login", response=api_response(AuthTokenPairOut))
def login(request: HttpRequest, payload: AuthLoginIn):
    """Проверяет логин или контакт и выдаёт access/refresh токены."""
    return login_user(payload.identifier, payload.password)


@router.post("/auth/refresh", response=api_response(AuthTokenPairOut))
def refresh(request: HttpRequest, payload: RefreshTokenIn):
    """Ротирует refresh-токен и выпускает новую пару токенов."""
    return refresh_token_pair(payload.refresh_token)


@router.post("/auth/logout", response=api_response({204: None}))
def logout(request: HttpRequest, payload: RefreshTokenIn):
    """Отзывает refresh-сессию и все выпущенные для неё access-токены."""
    revoke_refresh_token(payload.refresh_token)
    return 204, None


@router.get("/me", response=api_response(MeOut), auth=access_token_auth)
def get_me(request: HttpRequest):
    """Возвращает профиль и контексты ролей владельца access-токена."""
    return get_user_context(request_user_id(request))
