from django.db.models import QuerySet

from apps.identity_access.models import User
from apps.organizations.models import Organization
from apps.organizations.models import OrganizationMember


def list_organizations(user_id: int) -> QuerySet[Organization]:
    """Возвращает организации, доступные организатору или администратору."""
    user = User.objects.filter(pk=user_id).only("is_superuser", "is_platform_admin").first()
    if user is not None and (user.is_superuser or user.is_platform_admin):
        return Organization.objects.order_by("name", "id")
    return Organization.objects.filter(
        members__user_id=user_id,
        members__role=OrganizationMember.Role.ORGANIZER,
    ).distinct().order_by("name", "id")
