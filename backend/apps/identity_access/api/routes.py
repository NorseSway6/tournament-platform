from django.http import HttpRequest
from ninja import Router

from apps.identity_access.schemas import MeOut
from apps.identity_access.selectors import get_temporary_me
from config.api_errors import api_response


router = Router(tags=["Identity"])


@router.get("/me", response=api_response(MeOut))
def get_me(request: HttpRequest):
    """Возвращает профиль и области временных ролей для построения меню."""
    return get_temporary_me()
