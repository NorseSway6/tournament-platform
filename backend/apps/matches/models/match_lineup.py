from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class MatchLineup(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"

    match = models.ForeignKey("matches.Match", on_delete=models.PROTECT, related_name="lineups")
    entry = models.ForeignKey("teams.TournamentEntry", on_delete=models.PROTECT, related_name="lineups")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    reject_reason = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["match", "entry"], name="matches_lineup_entry_uq"),
            models.CheckConstraint(
                condition=Q(status__in=["draft", "submitted", "accepted", "rejected"]),
                name="matches_lineup_status_ck",
            ),
        ]

    def clean(self):
        """Проверяет, что заявка принадлежит участнику конкретного матча."""
        if self.match_id and self.entry_id:
            if self.entry.tournament_id != self.match.tournament_id:
                raise ValidationError({"entry": "Entry must belong to the match tournament."})
            if self.entry_id not in (self.match.home_entry_id, self.match.away_entry_id):
                raise ValidationError({"entry": "Entry must be one of the match participants."})

    def __str__(self) -> str:
        """Возвращает краткое описание заявки на состав."""
        return f"Lineup for match {self.match_id}, entry {self.entry_id}"


class MatchLineupPlayer(models.Model):
    class Role(models.TextChoices):
        PLAYER = "player", "Player"
        CAPTAIN = "captain", "Captain"

    lineup = models.ForeignKey(MatchLineup, on_delete=models.CASCADE, related_name="players")
    entry_player = models.ForeignKey("teams.EntryPlayer", on_delete=models.PROTECT, related_name="lineup_slots")
    number_snapshot = models.PositiveSmallIntegerField()
    is_starter = models.BooleanField(default=False)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.PLAYER)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["lineup", "entry_player"], name="matches_lineup_player_uq"),
            models.UniqueConstraint(fields=["lineup", "number_snapshot"], name="matches_lineup_number_uq"),
            models.CheckConstraint(condition=Q(number_snapshot__gte=1, number_snapshot__lte=99), name="matches_lineup_number_ck"),
            models.CheckConstraint(
                condition=Q(role__in=["player", "captain"]),
                name="matches_lineup_role_ck",
            ),
        ]

    def clean(self):
        """Проверяет, что игрок входит в состав заявки на матч."""
        if self.lineup_id and self.entry_player_id and self.entry_player.entry_id != self.lineup.entry_id:
            raise ValidationError({"entry_player": "Player must belong to the lineup entry."})

    def __str__(self) -> str:
        """Показывает игрока в контексте заявки на состав."""
        return f"{self.lineup_id}: {self.entry_player}"

