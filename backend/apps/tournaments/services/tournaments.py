from config.domain_errors import DomainError
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

from apps.organizations.models import Organization, OrganizationMember
from apps.tournaments.models import Tournament, TournamentMember




def _validate_dates(data: dict) -> None:
    """Проверяет порядок дат турнира до сохранения."""
    starts_on = data.get("starts_on")
    ends_on = data.get("ends_on")
    if starts_on and ends_on and ends_on < starts_on:
        raise DomainError("ends_on must be on or after starts_on", 422)


def _validate_regulation(regulation: dict) -> None:
    """Проверяет поддерживаемую сейчас часть регламента таблицы."""
    if not isinstance(regulation, dict):
        raise DomainError("regulation must be an object", 422)
    standings = regulation.get("standings")
    if standings is None:
        return
    if not isinstance(standings, dict):
        raise DomainError("regulation.standings must be an object", 422)
    for key in ("points_for_win", "points_for_draw", "points_for_loss"):
        if key in standings and (
            not isinstance(standings[key], int)
            or isinstance(standings[key], bool)
            or standings[key] < 0
        ):
            raise DomainError(f"{key} must be a non-negative integer", 422)
    allowed_tie_breakers = {
        "points",
        "goal_difference",
        "goals_for",
        "team_name",
        "team_id",
    }
    tie_breakers = standings.get("tie_breakers")
    if tie_breakers is not None and (
        not isinstance(tie_breakers, list)
        or any(
            not isinstance(item, str) or item not in allowed_tie_breakers
            for item in tie_breakers
        )
    ):
        raise DomainError("tie_breakers contains an unsupported value", 422)


def _organizer_tournament(tournament_id: int) -> Tournament:
    """Находит турнир по ID; authorization scope will be added with identity access."""
    tournament = Tournament.objects.filter(pk=tournament_id).first()
    if tournament is None:
        raise DomainError("Tournament not found", 404)
    return tournament


def list_organizer_tournaments(organization_id: int, user_id: int) -> list[Tournament]:
    """Returns only tournaments inside the caller's assigned organizer scope."""
    if not Organization.objects.filter(pk=organization_id).exists():
        raise DomainError("Organization not found", 404)
    User = get_user_model()
    user = User.objects.filter(pk=user_id).only("is_superuser", "is_platform_admin").first()
    if user and (user.is_superuser or user.is_platform_admin or OrganizationMember.objects.filter(
        user_id=user_id,
        role=OrganizationMember.Role.ORGANIZER,
        organization_id=organization_id,
    ).exists()):
        queryset = Tournament.objects.filter(organization_id=organization_id)
    else:
        granted_ids = TournamentMember.objects.filter(
            user_id=user_id,
            role=TournamentMember.Role.ORGANIZER,
            tournament__organization_id=organization_id,
        ).values_list("tournament_id", flat=True)
        queryset = Tournament.objects.filter(
            organization_id=organization_id, pk__in=granted_ids
        )
    return list(queryset.order_by("id"))


def get_organizer_tournament(tournament_id: int) -> Tournament:
    """Возвращает подробности турнира организатора."""
    return _organizer_tournament(tournament_id)


def create_organizer_tournament(data: dict) -> Tournament:
    """Создаёт турнир в организации, явно выбранной клиентом."""
    _validate_dates(data)
    _validate_regulation(data.get("regulation", {}))
    organization_id = data.pop("organization_id", None)
    organization = Organization.objects.filter(pk=organization_id).first()
    if organization is None:
        raise DomainError("Organization not found", 404)
    try:
        with transaction.atomic():
            tournament = Tournament(organization=organization, **data)
            tournament.full_clean()
            tournament.save()
            return tournament
    except ValidationError as error:
        raise DomainError(
            "Tournament validation failed", 422, validation_error=error
        ) from error
    except IntegrityError as error:
        raise DomainError("Tournament slug already exists for this organization", 409) from error


def update_organizer_tournament(tournament_id: int, data: dict) -> Tournament:
    """Partially updates tournament fields while retaining its organization."""
    if not data:
        raise DomainError("At least one field must be provided", 422)
    if "regulation" in data:
        _validate_regulation(data["regulation"])
    try:
        with transaction.atomic():
            tournament = Tournament.objects.select_for_update().get(pk=tournament_id)
            proposed_dates = {
                "starts_on": data.get("starts_on", tournament.starts_on),
                "ends_on": data.get("ends_on", tournament.ends_on),
            }
            _validate_dates(proposed_dates)
            for field, value in data.items():
                setattr(tournament, field, value)
            tournament.full_clean()
            tournament.save()
            return tournament
    except Tournament.DoesNotExist:
        return _organizer_tournament(tournament_id)
    except ValidationError as error:
        raise DomainError(
            "Tournament validation failed", 422, validation_error=error
        ) from error
    except IntegrityError as error:
        raise DomainError("Tournament slug already exists for this organization", 409) from error


def replace_organizer_regulation(tournament_id: int, regulation: dict) -> Tournament:
    """Целиком заменяет JSON-регламент принадлежащего организатору турнира."""
    _validate_regulation(regulation)
    tournament = _organizer_tournament(tournament_id)
    tournament.regulation = regulation
    tournament.save(update_fields=["regulation", "updated_at"])
    return tournament


def delete_organizer_tournament(tournament_id: int) -> None:
    """Удаляет турнир только до появления заявок и матчей."""
    tournament = _organizer_tournament(tournament_id)
    if tournament.entries.exists() or tournament.matches.exists():
        raise DomainError("Tournament with entries or matches cannot be deleted", 409)
    tournament.delete()


def organizer_entries(tournament_id: int) -> list:
    """Lists entry applications with team, captain, and active roster size."""
    tournament = _organizer_tournament(tournament_id)
    return list(
        tournament.entries.select_related("team", "team__captain")
        .annotate(player_count=Count("players", filter=Q(players__status="active")))
        .order_by("submitted_at", "id")
    )
