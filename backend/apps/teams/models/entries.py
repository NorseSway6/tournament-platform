from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.teams.models.player import Player
from apps.teams.models.team import Team
from apps.tournaments.models.tournament import Tournament


class TournamentEntry(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"
        WITHDRAWN = "withdrawn", "Withdrawn"

    tournament = models.ForeignKey(Tournament, on_delete=models.PROTECT, related_name="entries")
    team = models.ForeignKey(Team, on_delete=models.PROTECT, related_name="entries")
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    submitted_at = models.DateTimeField(default=timezone.now, editable=False)
    decision_comment = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["tournament", "status"], name="entries_tournament_status_idx")
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["tournament", "team"], name="entries_tournament_team_uq"
            ),
            models.CheckConstraint(
                condition=Q(status__in=["pending", "accepted", "rejected", "withdrawn"]),
                name="entries_status_valid_ck",
            ),
        ]

    def __str__(self) -> str:
        """Показывает команду и турнир в административных списках."""
        return f"{self.team.name} — {self.tournament.name}"


class EntryPlayer(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        REMOVED = "removed", "Removed"

    entry = models.ForeignKey(TournamentEntry, on_delete=models.PROTECT, related_name="players")
    tournament = models.ForeignKey(
        Tournament,
        null=True,
        on_delete=models.PROTECT,
        related_name="entry_players",
        editable=False,
    )
    player = models.ForeignKey(Player, on_delete=models.PROTECT, related_name="entry_memberships")
    number = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["entry", "player"], name="entries_player_uq"),
            models.UniqueConstraint(
                fields=["tournament", "player"],
                condition=Q(status="active"),
                name="entries_tournament_player_uq",
            ),
            models.UniqueConstraint(
                fields=["entry", "number"],
                condition=Q(status="active"),
                name="entries_active_number_uq",
            ),
            models.CheckConstraint(
                condition=Q(number__gte=1, number__lte=99), name="entries_number_range_ck"
            ),
            models.CheckConstraint(
                condition=Q(status__in=["active", "removed"]),
                name="entries_player_status_ck",
            ),
        ]

    def __str__(self) -> str:
        """Показывает игрока и его игровой номер."""
        return f"{self.player} #{self.number}"

    def save(self, *args, **kwargs):
        """Держит турнир записи в соответствии с турниром заявки."""
        if self.entry_id and self.tournament_id != self.entry.tournament_id:
            self.tournament_id = self.entry.tournament_id
            update_fields = kwargs.get("update_fields")
            if update_fields is not None:
                kwargs["update_fields"] = {*update_fields, "tournament"}
        super().save(*args, **kwargs)
