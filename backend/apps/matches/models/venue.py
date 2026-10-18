from django.db import models

class Venue(models.Model):
    organization = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT, related_name="venues")
    name = models.CharField(max_length=150)
    address = models.CharField(max_length=300, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization", "name"], name="matches_venue_name_uq")]

    def __str__(self) -> str:
        """Возвращает название площадки для админки и журналов."""
        return self.name
