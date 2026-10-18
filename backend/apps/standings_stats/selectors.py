from django.db.models import QuerySet

from apps.matches.models import Match
from apps.teams.models import TournamentEntry
from apps.tournaments.models import Stage, Tournament


def accepted_entries(tournament: Tournament) -> QuerySet[TournamentEntry]:
    """Возвращает принятые заявки турнира с данными команд"""
    return (
        TournamentEntry.objects.filter(
            tournament=tournament,
            status=TournamentEntry.Status.ACCEPTED,
        )
        .select_related("team")
        .order_by("team__name", "team_id", "id")
    )


def completed_stage_matches(tournament: Tournament) -> QuerySet[Match]:
    """Выбирает подтверждённые матчи с результатом для расчёта таблиц"""
    return (
        Match.objects.filter(
            tournament=tournament,
            status=Match.Status.CONFIRMED,
            home_entry__status=TournamentEntry.Status.ACCEPTED,
            away_entry__status=TournamentEntry.Status.ACCEPTED,
            home_score__isnull=False,
            away_score__isnull=False,
        )
        .select_related("stage", "home_entry__team", "away_entry__team")
        .order_by("stage__ord", "stage_id", "id")
    )


def tournament_stages(tournament: Tournament) -> QuerySet[Stage]:
    """Возвращает этапы турнира в порядке проведения"""
    return tournament.stages.order_by("ord", "id")
