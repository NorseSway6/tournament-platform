from django.db import models
from django.db.models import F, Q

from apps.organizations.models import Organization


class Tournament(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        REGISTRATION = "registration", "Registration"
        ONGOING = "ongoing", "Ongoing"
        FINISHED = "finished", "Finished"

    class Visibility(models.TextChoices):
        PUBLIC = "public", "Public"
        UNLISTED = "unlisted", "Unlisted"
        PRIVATE = "private", "Private"

    organization = models.ForeignKey(
        Organization, on_delete=models.PROTECT, related_name="tournaments"
    )
    slug = models.SlugField(max_length=64)
    name = models.CharField(max_length=200)
    season = models.CharField(max_length=50, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    visibility = models.CharField(
        max_length=20,
        choices=Visibility.choices,
        default=Visibility.PUBLIC,
        db_index=True,
    )
    regulation = models.JSONField(default=dict, blank=True)

    registration_deadline = models.DateTimeField(null=True, blank=True)
    starts_on = models.DateField(null=True, blank=True)
    ends_on = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["status", "starts_on"], name="tournaments_status_start_idx")
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "slug"], name="tournaments_org_slug_uq"
            ),
            models.CheckConstraint(
                condition=Q(status__in=["draft", "registration", "ongoing", "finished"]),
                name="tournaments_status_valid_ck",
            ),
            models.CheckConstraint(
                condition=Q(visibility__in=["public", "unlisted", "private"]),
                name="tournaments_visibility_valid_ck",
            ),
            models.CheckConstraint(
                condition=Q(starts_on__isnull=True)
                | Q(ends_on__isnull=True)
                | Q(ends_on__gte=F("starts_on")),
                name="tournaments_dates_ck",
            ),
        ]

    def __str__(self) -> str:
        """Возвращает название турнира для админки и журналов."""
        return self.name
