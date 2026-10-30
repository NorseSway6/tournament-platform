from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError

from apps.identity_access.selectors import get_active_user_by_identifier
from apps.organizations.models import Organization, OrganizationMember
from config.domain_errors import ConflictError, DomainValidationError, NotFoundError


def create_organization(data: dict, creator_id: int) -> Organization:
    """Проверяет и создает организацию, преобразуя конфликты в API-ошибки"""
    organization = Organization(**data)
    try:
        with transaction.atomic():
            organization.full_clean(validate_unique=False, validate_constraints=False)
            try:
                organization.save()
            except IntegrityError as error:
                raise ConflictError(
                    "Organization slug already exists", code="slug_taken"
                ) from error
            OrganizationMember.objects.get_or_create(
                user_id=creator_id,
                organization=organization,
                role=OrganizationMember.Role.ORGANIZER,
            )
    except ValidationError as error:
        raise DomainValidationError(
            "Organization validation failed", validation_error=error
        ) from error
    return organization


def update_organization(organization_id: int, changes: dict) -> Organization:
    """Частично обновляет организацию после полной проверки модели"""
    if not changes:
        raise DomainValidationError("At least one field must be provided")
    changes = dict(changes)
    for field, value in changes.items():
        if value is None:
            raise DomainValidationError(f"{field} cannot be null")

    try:
        with transaction.atomic():
            organization = (
                Organization.objects.select_for_update().filter(pk=organization_id).first()
            )
            if organization is None:
                raise NotFoundError("Organization not found")
            for field, value in changes.items():
                setattr(organization, field, value)
            organization.full_clean(validate_unique=False, validate_constraints=False)
            try:
                organization.save()
            except IntegrityError as error:
                raise ConflictError(
                    "Organization slug already exists", code="slug_taken"
                ) from error
            return organization
    except ValidationError as error:
        raise DomainValidationError(
            "Organization validation failed", validation_error=error
        ) from error


def delete_organization(organization_id: int) -> None:
    """Удаляет организацию только если на нее не ссылаются другие сущности"""
    try:
        with transaction.atomic():
            organization = (
                Organization.objects.select_for_update().filter(pk=organization_id).first()
            )
            if organization is None:
                raise NotFoundError("Organization not found")
            organization.delete()
    except ProtectedError as error:
        raise ConflictError(
            "Organization is referenced by tournaments, venues, or audit records",
            code="organization_in_use",
        ) from error


def add_organization_member(
    organization_id: int, identifier: str, role: str
) -> tuple[OrganizationMember, bool]:
    """Добавляет пользователя в организацию по username или email."""
    if role not in OrganizationMember.Role.values:
        raise DomainValidationError("Unsupported organization member role")
    user = get_active_user_by_identifier(identifier)
    if user is None:
        raise NotFoundError("Active user not found")
    with transaction.atomic():
        organization = Organization.objects.select_for_update().filter(pk=organization_id).first()
        if organization is None:
            raise NotFoundError("Organization not found")
        return OrganizationMember.objects.get_or_create(
            organization=organization,
            user=user,
            role=role,
        )


def remove_organization_member(organization_id: int, member_id: int) -> None:
    """Удаляет членство, не оставляя организацию без организатора."""
    with transaction.atomic():
        organization = Organization.objects.select_for_update().filter(pk=organization_id).first()
        if organization is None:
            raise NotFoundError("Organization not found")
        membership = OrganizationMember.objects.filter(
            pk=member_id, organization=organization
        ).first()
        if membership is None:
            raise NotFoundError("Organization member not found")
        if membership.role == OrganizationMember.Role.ORGANIZER:
            has_another_organizer = (
                OrganizationMember.objects.filter(
                    organization=organization,
                    role=OrganizationMember.Role.ORGANIZER,
                )
                .exclude(pk=membership.pk)
                .exists()
            )
            if not has_another_organizer:
                raise ConflictError("Cannot remove the last organizer", code="last_organizer")
        membership.delete()
