from django.db import models
from django.db.models import Q

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
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)

    class Meta:
        indexes = [models.Index(fields=["tournament", "status"], name="entries_tournament_status_idx")]
        constraints = [
            models.UniqueConstraint(fields=["tournament", "team"], name="entries_tournament_team_uq"),
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
    player = models.ForeignKey(Player, on_delete=models.PROTECT, related_name="entry_memberships")
    number = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["entry", "player"], name="entries_player_uq"),
            models.UniqueConstraint(
                fields=["entry", "number"], condition=Q(status="active"), name="entries_active_number_uq"
            ),
            models.CheckConstraint(condition=Q(number__gte=1, number__lte=99), name="entries_number_range_ck"),
            models.CheckConstraint(
                condition=Q(status__in=["active", "removed"]),
                name="entries_player_status_ck",
            ),
        ]

    def __str__(self) -> str:
        """Показывает игрока и его игровой номер."""
        return f"{self.player} #{self.number}"
