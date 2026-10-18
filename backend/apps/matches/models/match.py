from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q

from apps.tournaments.models.round import Round as TournamentRound


class Match(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        LINEUPS_OPEN = "lineups_open", "Match registration"
        LIVE = "live", "Live"
        FINISHED = "finished", "Finished"
        CONFIRMED = "confirmed", "Confirmed"
        POSTPONED = "postponed", "Postponed"
        CANCELLED = "cancelled", "Cancelled"
        TECHNICAL = "technical", "Technical result"

    class ResultType(models.TextChoices):
        PLAYED = "played", "Played"
        TECH_WIN_HOME = "tech_win_home", "Home technical win"
        TECH_WIN_AWAY = "tech_win_away", "Away technical win"
        WALKOVER = "walkover", "Walkover"

    tournament = models.ForeignKey("tournaments.Tournament", on_delete=models.PROTECT, related_name="matches")
    stage = models.ForeignKey("tournaments.Stage", on_delete=models.PROTECT, related_name="matches")
    round = models.ForeignKey(TournamentRound, null=True, blank=True, on_delete=models.PROTECT, related_name="matches")
    home_entry = models.ForeignKey("teams.TournamentEntry", null=True, blank=True, on_delete=models.PROTECT, related_name="home_matches")
    away_entry = models.ForeignKey("teams.TournamentEntry", null=True, blank=True, on_delete=models.PROTECT, related_name="away_matches")

    venue = models.ForeignKey("matches.Venue", null=True, blank=True, on_delete=models.SET_NULL, related_name="matches")
    scheduled_at = models.DateTimeField(null=True, blank=True)
    duration_min = models.PositiveSmallIntegerField(default=60)
    scheduled_end = models.DateTimeField(null=True, blank=True, editable=False)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SCHEDULED)
    result_type = models.CharField(max_length=20, choices=ResultType.choices, default=ResultType.PLAYED)

    home_score = models.PositiveSmallIntegerField(null=True, blank=True)
    away_score = models.PositiveSmallIntegerField(null=True, blank=True)

    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["tournament", "scheduled_at"], name="matches_tourn_sched_idx"),
            models.Index(fields=["status", "scheduled_at"], name="matches_status_sched_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(home_entry__isnull=True) | Q(away_entry__isnull=True) | ~Q(home_entry=F("away_entry")),
                name="matches_distinct_teams_ck",
            ),
            models.CheckConstraint(condition=Q(duration_min__gte=1), name="matches_duration_positive_ck"),
            models.CheckConstraint(
                condition=(Q(scheduled_at__isnull=True) & Q(scheduled_end__isnull=True))
                | (Q(scheduled_at__isnull=False) & Q(scheduled_end__gt=F("scheduled_at"))),
                name="matches_end_after_start_ck",
            ),
            models.CheckConstraint(
                condition=(Q(home_score__isnull=True) & Q(away_score__isnull=True))
                | (Q(home_score__isnull=False) & Q(away_score__isnull=False)),
                name="matches_scores_are_pair_ck",
            ),
            models.CheckConstraint(
                condition=~Q(status__in=["finished", "confirmed", "technical"])
                | (Q(home_score__isnull=False) & Q(away_score__isnull=False)),
                name="matches_result_status_has_score_ck",
            ),
            models.CheckConstraint(
                condition=Q(status__in=["scheduled", "lineups_open", "live", "finished", "confirmed", "postponed", "cancelled", "technical"]),
                name="matches_status_valid_ck",
            ),
            models.CheckConstraint(
                condition=Q(result_type__in=["played", "tech_win_home", "tech_win_away", "walkover"]),
                name="matches_result_type_valid_ck",
            ),
        ]

    def clean(self):
        """Проверяет, что этап, тур и заявки принадлежат этому турниру."""
        errors = {}
        if self.stage_id and self.tournament_id and self.stage.tournament_id != self.tournament_id:
            errors["stage"] = "Stage must belong to the selected tournament."
        if self.round_id and self.stage_id and self.round.stage_id != self.stage_id:
            errors["round"] = "Round must belong to the selected stage."
        for field_name in ("home_entry", "away_entry"):
            entry = getattr(self, field_name, None)
            if entry and self.tournament_id and entry.tournament_id != self.tournament_id:
                errors[field_name] = "Team entry must belong to the selected tournament."
        if self.home_entry_id and self.home_entry_id == self.away_entry_id:
            errors["away_entry"] = "Home and away entries must be different."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        """Пересчитывает плановое время окончания матча перед сохранением."""
        self.scheduled_end = (
            self.scheduled_at + timedelta(minutes=self.duration_min) if self.scheduled_at else None
        )
        update_fields = kwargs.get("update_fields")
        if update_fields is not None and {"scheduled_at", "duration_min"} & set(update_fields):
            kwargs["update_fields"] = {*update_fields, "scheduled_end"}
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        """Возвращает краткое название матча для админки и журналов."""
        return f"Match #{self.pk} — {self.tournament.name}"
