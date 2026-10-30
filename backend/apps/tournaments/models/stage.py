from django.db import models

from apps.tournaments.models.tournament import Tournament


class Stage(models.Model):
    class Kind(models.TextChoices):
        LEAGUE = "league", "League"
        GROUPS = "groups", "Groups"
        PLAYOFF = "playoff", "Play-off"

    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE, related_name="stages")
    ord = models.PositiveSmallIntegerField()
    kind = models.CharField(max_length=20, choices=Kind.choices)
    name = models.CharField(max_length=100)

    class Meta:
        ordering = ["ord"]
        constraints = [
            models.UniqueConstraint(fields=["tournament", "ord"], name="tournaments_stage_ord_uq"),
            models.CheckConstraint(
                condition=models.Q(ord__gte=1), name="tournaments_stage_ord_positive_ck"
            ),
            models.CheckConstraint(
                condition=models.Q(kind__in=["league", "groups", "playoff"]),
                name="tournaments_stage_kind_ck",
            ),
        ]

    def __str__(self) -> str:
        """Возвращает название этапа для админки и журналов."""
        return self.name
