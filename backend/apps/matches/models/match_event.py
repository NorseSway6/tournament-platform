import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q


class MatchEvent(models.Model):
    class Period(models.TextChoices):
        FIRST_HALF = "first_half", "First half"
        HALF_TIME = "half_time", "Half time"
        SECOND_HALF = "second_half", "Second half"
        EXTRA_TIME_FIRST = "extra_time_first", "First extra time"
        EXTRA_TIME_SECOND = "extra_time_second", "Second extra time"
        PENALTIES = "penalties", "Penalties"

    class Source(models.TextChoices):
        JUDGE = "judge", "Judge"
        ORGANIZER = "organizer", "Organizer"
        SYSTEM = "system", "System"

    class Type(models.TextChoices):
        GOAL = "goal"
        OWN_GOAL = "own_goal"
        YELLOW = "yellow"
        RED = "red"
        SUBSTITUTION = "sub"
        PERIOD_START = "period_start"
        PERIOD_END = "period_end"
        PAUSE = "pause"
        RESUME = "resume"
        FINISH = "finish"
        VOID = "void"
        REVIEW_OK = "review_ok"
        NOTE = "note"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    match = models.ForeignKey("matches.Match", on_delete=models.PROTECT, related_name="events")
    seq = models.PositiveIntegerField()
    device_id = models.UUIDField(null=True, blank=True)
    client_seq = models.PositiveIntegerField(null=True, blank=True)
    type = models.CharField(max_length=20, choices=Type.choices)
    entry = models.ForeignKey(
        "teams.TournamentEntry", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    player = models.ForeignKey(
        "teams.EntryPlayer",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="match_events",
    )
    related_player = models.ForeignKey(
        "teams.EntryPlayer",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="related_match_events",
    )
    period = models.CharField(max_length=24, choices=Period.choices, null=True, blank=True)
    clock_ms = models.PositiveBigIntegerField(null=True, blank=True)
    minute = models.PositiveSmallIntegerField(null=True, blank=True)
    second = models.PositiveSmallIntegerField(null=True, blank=True)
    client_created_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    needs_review = models.BooleanField(default=False)
    source = models.CharField(max_length=16, choices=Source.choices, default=Source.JUDGE)
    target_event = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="revisions",
    )

    class Meta:
        ordering = ["match_id", "seq"]
        constraints = [
            models.UniqueConstraint(fields=["match", "seq"], name="matches_event_seq_uq"),
            models.UniqueConstraint(
                fields=["match", "device_id", "client_seq"],
                condition=Q(device_id__isnull=False, client_seq__isnull=False),
                name="matches_event_device_seq_uq",
            ),
            models.CheckConstraint(condition=Q(seq__gte=1), name="matches_event_seq_positive_ck"),
            models.CheckConstraint(
                condition=Q(client_seq__isnull=True) | Q(client_seq__gte=1),
                name="matches_event_client_seq_positive_ck",
            ),
            models.CheckConstraint(
                condition=~Q(type__in=["void", "review_ok"]) | Q(target_event__isnull=False),
                name="matches_event_target_required_ck",
            ),
            models.CheckConstraint(
                condition=Q(
                    type__in=[
                        "goal",
                        "own_goal",
                        "yellow",
                        "red",
                        "sub",
                        "period_start",
                        "period_end",
                        "pause",
                        "resume",
                        "finish",
                        "void",
                        "review_ok",
                        "note",
                    ]
                ),
                name="matches_event_type_valid_ck",
            ),
            models.CheckConstraint(
                condition=Q(minute__isnull=True) | Q(minute__gte=0),
                name="matches_event_minute_nonnegative_ck",
            ),
            models.CheckConstraint(
                condition=Q(second__isnull=True) | Q(second__gte=0, second__lte=59),
                name="matches_event_second_range_ck",
            ),
            models.CheckConstraint(
                condition=Q(target_event__isnull=True) | ~Q(target_event=F("id")),
                name="matches_event_not_self_target_ck",
            ),
        ]

    def __str__(self) -> str:
        """Показывает номер события и его тип."""
        return f"{self.match_id}:{self.seq} {self.type}"

    def clean(self):
        """Проверяет принадлежность события матчу, команде и игроку."""
        if self.target_event_id and self.match_id and self.target_event.match_id != self.match_id:
            raise ValidationError({"target_event": "Target event must belong to the same match."})
        if self.entry_id and self.match_id and self.entry.tournament_id != self.match.tournament_id:
            raise ValidationError({"entry": "Entry must belong to the match tournament."})
        if self.player_id and self.entry_id and self.player.entry_id != self.entry_id:
            raise ValidationError({"player": "Player must belong to the selected entry."})
        if (
            self.related_player_id
            and self.entry_id
            and self.related_player.entry_id != self.entry_id
        ):
            raise ValidationError(
                {"related_player": "Related player must belong to the selected entry."}
            )
