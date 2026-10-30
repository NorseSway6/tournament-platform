from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.db import models


def validate_timezone_name(value: str) -> None:
    """Отклоняет значения с неизвестными часовыми поясами"""
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError) as error:
        from django.core.exceptions import ValidationError

        raise ValidationError("Enter a valid IANA timezone name.") from error


class Organization(models.Model):
    slug = models.SlugField(max_length=64, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    timezone = models.CharField(max_length=64, default="UTC", validators=[validate_timezone_name])
    contacts = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class OrganizationMember(models.Model):
    """User membership and organization-scoped permissions."""

    class Role(models.TextChoices):
        ORGANIZER = "organizer", "Organizer"
        REFEREE = "referee", "Referee"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="organization_memberships"
    )
    role = models.CharField(max_length=16, choices=Role.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "user", "role"],
                name="organizations_member_role_uq",
            ),
        ]
        indexes = [models.Index(fields=["user", "role"], name="org_member_user_role_idx")]

    def __str__(self) -> str:
        """Describes the user's role within the organization."""
        return f"{self.user} — {self.role} ({self.organization})"
