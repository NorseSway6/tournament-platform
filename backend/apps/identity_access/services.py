from config.domain_errors import DomainError
import hashlib
import secrets
from datetime import timedelta

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.core import signing
from django.db.models import Q

from apps.identity_access.models import TokenSession, User

ACCESS_TOKEN_SALT = "football-platform.access"
ACCESS_TOKEN_TTL_SECONDS = 15 * 60
REFRESH_TOKEN_TTL = timedelta(days=30)






@transaction.atomic
def create_user(data: dict) -> User:
    """Создаёт учетную запись с паролем и хотя бы одним контактным идентификатором."""
    email = (data.get("email") or "").strip().lower() or None
    phone = (data.get("phone") or "").strip() or None
    telegram_id = data.get("telegram_id")
    if not (email or phone or telegram_id):
        raise DomainError("At least one of email, phone, or telegram_id is required", 422)

    username = data["username"].strip()
    if not username:
        raise DomainError("username cannot be empty", 422)
    user = User(
        username=username,
        email=email,
        phone=phone,
        telegram_id=telegram_id,
        telegram_username=data.get("telegram_username", "").strip(),
        display_name=data.get("display_name", "").strip(),
        first_name=data.get("first_name", "").strip(),
        last_name=data.get("last_name", "").strip(),
    )
    try:
        validate_password(data["password"], user=user)
    except ValidationError as error:
        raise DomainError(
            "Password validation failed",
            422,
            validation_error=error,
            validation_location=("body", "password"),
        ) from error

    user.set_password(data["password"])
    try:
        user.full_clean()
    except ValidationError as error:
        error_items = (
            item
            for field_errors in error.error_dict.values()
            for item in field_errors
        ) if hasattr(error, "error_dict") else iter(error.error_list)
        if any(item.code == "unique" for item in error_items):
            raise DomainError(
                "One or more user identifiers are already in use",
                409,
                validation_error=error,
            ) from error
        raise DomainError(
            "User data validation failed", 422, validation_error=error
        ) from error
    try:
        user.save()
    except IntegrityError as error:
        raise DomainError(
            "Username, email, phone, or telegram_id is already in use", 409
        ) from error
    return user


def _token_hash(token: str) -> str:
    """Хеширует refresh token для хранения в базе данных."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _access_token(user: User, session: TokenSession) -> str:
    """Подписывает короткоживущий access token с ID пользователя и сессии."""
    return signing.dumps(
        {"user_id": user.pk, "session_id": str(session.pk)},
        salt=ACCESS_TOKEN_SALT,
        compress=True,
    )


def _token_pair(user: User, session: TokenSession, refresh_token: str) -> dict:
    """Собирает ответ с новой парой access и refresh токенов."""
    return {
        "access_token": _access_token(user, session),
        "refresh_token": refresh_token,
        "token_type": "Bearer",
        "expires_in": ACCESS_TOKEN_TTL_SECONDS,
        "refresh_expires_at": session.expires_at,
        "user": user,
    }


def create_token_pair(user: User) -> dict:
    """Создаёт refresh-сессию и выдаёт пару access/refresh токенов."""
    refresh_token = secrets.token_urlsafe(48)
    session = TokenSession.objects.create(
        user=user,
        refresh_token_hash=_token_hash(refresh_token),
        expires_at=timezone.now() + REFRESH_TOKEN_TTL,
    )
    return _token_pair(user, session, refresh_token)


def login_user(identifier: str, password: str) -> dict:
    """Проверяет username, email или телефон и создаёт token-сессию."""
    user = (
        User.objects.filter(
            Q(username__iexact=identifier)
            | Q(email__iexact=identifier)
            | Q(phone=identifier)
        )
        .first()
    )
    if user is None or not user.is_active or not user.check_password(password):
        raise DomainError("Invalid username or password", 401)
    return create_token_pair(user)


@transaction.atomic
def refresh_token_pair(refresh_token: str) -> dict:
    """Ротирует refresh token и выдаёт новый access token той же сессии."""
    token_session = (
        TokenSession.objects.select_for_update()
        .select_related("user")
        .filter(refresh_token_hash=_token_hash(refresh_token), revoked_at__isnull=True)
        .first()
    )
    now = timezone.now()
    if (
        token_session is None
        or token_session.expires_at <= now
        or not token_session.user.is_active
    ):
        raise DomainError("Refresh token is invalid or expired", 401)

    next_refresh_token = secrets.token_urlsafe(48)
    token_session.refresh_token_hash = _token_hash(next_refresh_token)
    token_session.save(update_fields=["refresh_token_hash"])
    return _token_pair(token_session.user, token_session, next_refresh_token)


def revoke_refresh_token(refresh_token: str) -> None:
    """Отзывает сессию по refresh token, делая связанные access tokens недействительными."""
    TokenSession.objects.filter(
        refresh_token_hash=_token_hash(refresh_token), revoked_at__isnull=True
    ).update(revoked_at=timezone.now())


def user_from_access_token(token: str) -> User | None:
    """Проверяет подпись, срок действия и активность access-token сессии."""
    try:
        payload = signing.loads(
            token,
            salt=ACCESS_TOKEN_SALT,
            max_age=ACCESS_TOKEN_TTL_SECONDS,
        )
    except signing.BadSignature:
        return None
    if not isinstance(payload, dict):
        return None
    token_session = (
        TokenSession.objects.select_related("user")
        .filter(
            pk=payload.get("session_id"),
            user_id=payload.get("user_id"),
            revoked_at__isnull=True,
            expires_at__gt=timezone.now(),
            user__is_active=True,
        )
        .first()
    )
    return token_session.user if token_session is not None else None
