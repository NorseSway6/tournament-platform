from django.db.models import Prefetch, QuerySet

from apps.tournaments.models import Stage, Tournament

PUBLIC_STATUSES = [
    Tournament.Status.REGISTRATION,
    Tournament.Status.ONGOING,
    Tournament.Status.FINISHED,
]


def public_tournaments(
    status: str | None = None, stage_kind: str | None = None
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
    return (
        queryset.distinct()
        .select_related("organization")
        .prefetch_related(
            Prefetch("stages", queryset=Stage.objects.order_by("ord", "id"))
        )
    )


def get_public_tournament(tournament_id: int) -> Tournament | None:
    """Ищет турнир по ID среди доступных публичному API"""
    return public_tournaments().filter(pk=tournament_id).first()
