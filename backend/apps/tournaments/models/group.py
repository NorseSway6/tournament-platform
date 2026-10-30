from django.core.exceptions import ValidationError
from django.db import models

from apps.tournaments.models.stage import Stage


class Group(models.Model):
    """Группа внутри этапа формата группового турнира."""

    stage = models.ForeignKey(Stage, on_delete=models.CASCADE, related_name="groups")
    ord = models.PositiveSmallIntegerField()
    name = models.CharField(max_length=100)

    class Meta:
        ordering = ["ord", "id"]
        constraints = [
            models.UniqueConstraint(fields=["stage", "ord"], name="tournaments_group_ord_uq"),
            models.UniqueConstraint(fields=["stage", "name"], name="tournaments_group_name_uq"),
            models.CheckConstraint(
                condition=models.Q(ord__gte=1), name="tournaments_group_ord_positive_ck"
            ),
        ]

    def __str__(self) -> str:
        """Возвращает имя группы для админки и журналов."""
        return self.name

    def clean(self) -> None:
        """Группы допускаются только внутри этапа группового формата."""
        if self.stage_id and self.stage.kind != Stage.Kind.GROUPS:
            raise ValidationError({"stage": "Groups can only belong to a groups stage."})
