from django.core.exceptions import ValidationError
from django.db import models

from apps.tournaments.models.group import Group


class GroupEntry(models.Model):
    """Явное назначение принятой заявки в группу этапа."""

    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="entry_assignments")
    entry = models.ForeignKey(
        "teams.TournamentEntry",
        on_delete=models.PROTECT,
        related_name="group_assignments",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["group_id", "entry_id"]
        constraints = [
            models.UniqueConstraint(fields=["group", "entry"], name="tournaments_group_entry_uq"),
        ]

    def __str__(self) -> str:
        """Показывает команду и группу для административных списков."""
        return f"{self.entry.team} — {self.group}"

    def clean(self) -> None:
        """Проверяет, что заявка и группа относятся к одному турниру."""
        if (
            self.group_id
            and self.entry_id
            and self.group.stage.tournament_id != self.entry.tournament_id
        ):
            raise ValidationError({"entry": "Entry must belong to the group's tournament."})
