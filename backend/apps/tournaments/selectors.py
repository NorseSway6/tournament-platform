from django.db.models import Count, Exists, F, OuterRef, Prefetch, QuerySet

from apps.matches.models import MatchEvent
from apps.tournaments.models import Group, Round, Stage, Tournament

PUBLIC_STATUSES = [
    Tournament.Status.REGISTRATION,
    Tournament.Status.ONGOING,
    Tournament.Status.FINISHED,
]


def public_tournaments(
    status: str | None = None,
    stage_kind: str | None = None,
    search: str | None = None,
) -> QuerySet[Tournament]:
    """Возвращает публичные турниры с загруженной организацией и этапами"""
    queryset = Tournament.objects.filter(
        status__in=PUBLIC_STATUSES,
        visibility=Tournament.Visibility.PUBLIC,
    )
    if status is not None:
        queryset = queryset.filter(status=status)
    if stage_kind is not None:
        queryset = queryset.filter(stages__kind=stage_kind)
    if search is not None and search.strip():
        queryset = queryset.filter(name__icontains=search.strip())
    return (
        queryset.distinct()
        .select_related("organization")
        .prefetch_related(
            Prefetch(
                "stages",
                queryset=Stage.objects.order_by("ord", "id").prefetch_related(
                    Prefetch("groups", queryset=Group.objects.order_by("ord", "id")),
                    Prefetch("rounds", queryset=Round.objects.order_by("ord", "id")),
                ),
            )
        )
        .order_by(F("starts_on").desc(nulls_last=True), "name", "id")
    )


def get_public_tournament(tournament_id: int) -> Tournament | None:
    """Ищет турнир по ID среди доступных публичному API"""
    return public_tournaments().filter(pk=tournament_id).first()


def tournament_scorers(tournament_id: int) -> list[dict]:
    """Возвращает бомбардиров турнира по неотменённым голам."""
    voided_goals = MatchEvent.objects.filter(
        match_id=OuterRef("match_id"),
        type=MatchEvent.Type.VOID,
        target_event_id=OuterRef("pk"),
    )
    rows = (
        MatchEvent.objects.filter(
            match__tournament_id=tournament_id,
            type=MatchEvent.Type.GOAL,
            player__isnull=False,
        )
        .annotate(voided=Exists(voided_goals))
        .filter(voided=False)
        .values(
            "player__player_id",
            "player__player__last_name",
            "player__player__first_name",
            "player__player__middle_name",
            "entry__team_id",
            "entry__team__name",
        )
        .annotate(goals=Count("id"))
    )

    scorers: dict[int, dict] = {}
    for row in rows:
        player_id = row["player__player_id"]
        scorer = scorers.get(player_id)
        if scorer is None:
            scorer = {
                "player_id": player_id,
                "player_name": " ".join(
                    part
                    for part in (
                        row["player__player__last_name"],
                        row["player__player__first_name"],
                        row["player__player__middle_name"],
                    )
                    if part
                ),
                "team_id": row["entry__team_id"],
                "team_name": row["entry__team__name"],
                "goals": 0,
            }
            scorers[player_id] = scorer
        scorer["goals"] += row["goals"]

    return sorted(
        scorers.values(),
        key=lambda scorer: (
            -scorer["goals"],
            scorer["player_name"].casefold(),
            scorer["player_id"],
        ),
    )
