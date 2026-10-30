from django.contrib.auth import get_user_model

from apps.identity_access.models import User


def get_active_user_by_identifier(identifier: str) -> User | None:
    """Находит активного пользователя по username или email без учёта регистра."""
    value = identifier.strip()
    if not value:
        return None
    users = User.objects.filter(is_active=True)
    if "@" in value:
        return (
            users.filter(email__iexact=value).first()
            or users.filter(username__iexact=value).first()
        )
    return users.filter(username__iexact=value).first() or users.filter(email__iexact=value).first()


def get_me_profile(user_id: int) -> dict:
    """Returns identity-owned profile fields without importing domain modules."""
    user = get_user_model().objects.get(pk=user_id)
    return {
        "id": user.pk,
        "username": user.username,
        "display_name": user.display_name or user.get_full_name() or user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
    }
