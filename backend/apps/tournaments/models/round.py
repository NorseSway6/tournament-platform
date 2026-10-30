from django.db import models

from apps.tournaments.models.stage import Stage


class Round(models.Model):
    stage = models.ForeignKey(Stage, on_delete=models.CASCADE, related_name="rounds")
    ord = models.PositiveSmallIntegerField()
    name = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ["ord"]
        constraints = [
            models.UniqueConstraint(fields=["stage", "ord"], name="tournaments_round_ord_uq"),
            models.CheckConstraint(
                condition=models.Q(ord__gte=1), name="tournaments_round_ord_positive_ck"
            ),
        ]

    def __str__(self) -> str:
        """Возвращает заданное название тура или его порядковый номер."""
        return self.name or f"Round {self.ord}"
