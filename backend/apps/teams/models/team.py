from django.db import models


class Team(models.Model):
    name = models.CharField(max_length=150, db_index=True)
    captain = models.ForeignKey(
        "identity_access.User",
        on_delete=models.PROTECT,
        related_name="captained_teams",
    )
    city = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "id"]

    def __str__(self) -> str:
        """Возвращает название команды для админки и журналов."""
        return self.name
