from django.conf import settings
from django.db import models


class MatchOfficial(models.Model):
    """Связывает официальный персонал с матчем и его ролью."""

    class Role(models.TextChoices):
        REFEREE = "referee", "Referee"
        ASSISTANT_REFEREE = "assistant_referee", "Assistant referee"
        FOURTH_OFFICIAL = "fourth_official", "Fourth official"
        DELEGATE = "delegate", "Delegate"

    match = models.ForeignKey(
        "matches.Match", on_delete=models.CASCADE, related_name="official_assignments"
    )
    official = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="match_official_assignments",
    )
    role = models.CharField(max_length=32, choices=Role.choices)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["match", "official"], name="matches_official_person_uq"
            ),
            models.CheckConstraint(
                condition=models.Q(
                    role__in=[
                        "referee",
                        "assistant_referee",
                        "fourth_official",
                        "delegate",
                    ]
                ),
                name="matches_official_role_ck",
            ),
        ]

    def __str__(self) -> str:
        """Показывает официальное лицо, его роль и матч."""
        return f"{self.official} — {self.role} (match {self.match_id})"
