from django.db import models

from django.conf import settings
from django.db.models import Q

class Player(models.Model):
    last_name = models.CharField(max_length=100)
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="player_profile",
    )

    class Meta:
        indexes = [models.Index(fields=["last_name", "first_name"], name="teams_player_name_idx")]

    def __str__(self) -> str:
        """Возвращает ФИО игрока для админки и журналов."""
        return " ".join(part for part in (self.last_name, self.first_name, self.middle_name) if part)
