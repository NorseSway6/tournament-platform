from django.contrib.auth import get_user_model


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
