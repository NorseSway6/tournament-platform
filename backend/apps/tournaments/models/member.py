from django.conf import settings
from django.db import models


class TournamentMember(models.Model):
    """A user's permission assignment scoped to one tournament."""

    class Role(models.TextChoices):
        ORGANIZER = "organizer", "Organizer"

    tournament = models.ForeignKey(
        "tournaments.Tournament",
        on_delete=models.CASCADE,
        related_name="members",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tournament_memberships",
    )
    role = models.CharField(max_length=16, choices=Role.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tournament", "user", "role"],
                name="tournaments_member_role_uq",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "role"], name="tourn_member_user_role_idx")
        ]

    def __str__(self) -> str:
        """Describes the user's role within the tournament."""
        return f"{self.user} — {self.role} ({self.tournament})"
