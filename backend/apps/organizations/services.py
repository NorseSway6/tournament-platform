from config.domain_errors import DomainError
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError

from apps.organizations.models import Organization
from apps.organizations.models import OrganizationMember




def create_organization(data: dict, creator_id: int) -> Organization:
    """Проверяет и создает организацию, преобразуя конфликты в API-ошибки"""
    organization = Organization(**data)
    try:
        with transaction.atomic():
            organization.full_clean(validate_unique=False, validate_constraints=False)
            try:
                organization.save()
            except IntegrityError as error:
                raise DomainError(
                    "Organization slug already exists", 409
                ) from error
            from apps.identity_access.models import User

            creator = User.objects.only("is_superuser", "is_platform_admin").get(pk=creator_id)
            if not (creator.is_superuser or creator.is_platform_admin):
                OrganizationMember.objects.get_or_create(
                    user_id=creator_id,
                    organization=organization,
                    role=OrganizationMember.Role.ORGANIZER,
                )
    except ValidationError as error:
        raise DomainError(
            "Organization validation failed", 422, validation_error=error
        ) from error
    return organization


def update_organization(organization_id: int, changes: dict) -> Organization:
    """Частично обновляет организацию после полной проверки модели"""
    if not changes:
        raise DomainError("At least one field must be provided", 422)
    changes = dict(changes)
    for field, value in changes.items():
        if value is None:
            raise DomainError(f"{field} cannot be null", 422)

    try:
        with transaction.atomic():
            organization = (
                Organization.objects.select_for_update()
                .filter(pk=organization_id)
                .first()
            )
            if organization is None:
                raise DomainError("Organization not found", 404)
            for field, value in changes.items():
                setattr(organization, field, value)
            organization.full_clean(validate_unique=False, validate_constraints=False)
            try:
                organization.save()
            except IntegrityError as error:
                raise DomainError(
                    "Organization slug already exists", 409
                ) from error
            return organization
    except ValidationError as error:
        raise DomainError(
            "Organization validation failed", 422, validation_error=error
        ) from error


def delete_organization(organization_id: int) -> None:
    """Удаляет организацию только если на нее не ссылаются другие сущности"""
    try:
        with transaction.atomic():
            organization = (
                Organization.objects.select_for_update()
                .filter(pk=organization_id)
                .first()
            )
            if organization is None:
                raise DomainError("Organization not found", 404)
            organization.delete()
    except ProtectedError as error:
        raise DomainError(
            "Organization is referenced by tournaments, venues, or audit records",
            409,
        ) from error
