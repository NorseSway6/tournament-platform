from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count, Q

from apps.organizations.models import Organization, OrganizationMember
from apps.tournaments.models import Tournament, TournamentMember
from config.domain_errors import ConflictError, DomainValidationError, NotFoundError


def _validate_dates(data: dict) -> None:
    """Проверяет порядок дат турнира до сохранения."""
    starts_on = data.get("starts_on")
    ends_on = data.get("ends_on")
    if starts_on and ends_on and ends_on < starts_on:
        raise DomainValidationError("ends_on must be on or after starts_on")


def _validate_regulation(regulation: dict) -> None:
    """Проверяет поддерживаемую сейчас часть регламента таблицы."""
    if not isinstance(regulation, dict):
        raise DomainValidationError("regulation must be an object")
    standings = regulation.get("standings")
    if standings is None:
        return
    if not isinstance(standings, dict):
        raise DomainValidationError("regulation.standings must be an object")
    for key in ("points_for_win", "points_for_draw", "points_for_loss"):
        if key in standings and (
            not isinstance(standings[key], int)
            or isinstance(standings[key], bool)
            or standings[key] < 0
        ):
            raise DomainValidationError(f"{key} must be a non-negative integer")
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
            not isinstance(item, str) or item not in allowed_tie_breakers for item in tie_breakers
        )
    ):
        raise DomainValidationError("tie_breakers contains an unsupported value")


def _organizer_tournament(tournament_id: int) -> Tournament:
    """Находит турнир по ID; authorization scope will be added with identity access."""
    tournament = Tournament.objects.filter(pk=tournament_id).first()
    if tournament is None:
        raise NotFoundError("Tournament not found")
    return tournament


def list_organizer_tournaments(organization_id: int, user_id: int) -> list[Tournament]:
    """Returns only tournaments inside the caller's assigned organizer scope."""
    if not Organization.objects.filter(pk=organization_id).exists():
        raise NotFoundError("Organization not found")
    User = get_user_model()
    user = User.objects.filter(pk=user_id).only("is_superuser", "is_platform_admin").first()
    if user and (
        user.is_superuser
        or user.is_platform_admin
        or OrganizationMember.objects.filter(
            user_id=user_id,
            role=OrganizationMember.Role.ORGANIZER,
            organization_id=organization_id,
        ).exists()
    ):
        queryset = Tournament.objects.filter(organization_id=organization_id)
    else:
        granted_ids = TournamentMember.objects.filter(
            user_id=user_id,
            role=TournamentMember.Role.ORGANIZER,
            tournament__organization_id=organization_id,
        ).values_list("tournament_id", flat=True)
        queryset = Tournament.objects.filter(organization_id=organization_id, pk__in=granted_ids)
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
        raise NotFoundError("Organization not found")
    data["status"] = Tournament.Status.DRAFT
    try:
        with transaction.atomic():
            tournament = Tournament(organization=organization, **data)
            tournament.full_clean()
            tournament.save()
            return tournament
    except ValidationError as error:
        raise DomainValidationError(
            "Tournament validation failed", validation_error=error
        ) from error
    except IntegrityError as error:
        raise ConflictError(
            "Tournament slug already exists for this organization", code="slug_taken"
        ) from error


def update_organizer_tournament(tournament_id: int, data: dict) -> Tournament:
    """Partially updates tournament fields while retaining its organization."""
    if not data:
        raise DomainValidationError("At least one field must be provided")
    if "status" in data or "regulation" in data:
        raise DomainValidationError(
            "Use the explicit transition or regulation endpoints for these fields"
        )
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
        raise DomainValidationError(
            "Tournament validation failed", validation_error=error
        ) from error
    except IntegrityError as error:
        raise ConflictError(
            "Tournament slug already exists for this organization", code="slug_taken"
        ) from error


def replace_organizer_regulation(tournament_id: int, regulation: dict) -> Tournament:
    """Целиком заменяет JSON-регламент турнира до его старта."""
    _validate_regulation(regulation)
    with transaction.atomic():
        tournament = Tournament.objects.select_for_update().filter(pk=tournament_id).first()
        if tournament is None:
            raise NotFoundError("Tournament not found")
        if tournament.status not in (
            Tournament.Status.DRAFT,
            Tournament.Status.REGISTRATION,
        ):
            raise ConflictError(
                "Tournament regulation is frozen after the tournament starts",
                code="regulation_frozen",
            )
        tournament.regulation = regulation
        tournament.save(update_fields=["regulation", "updated_at"])
        return tournament


def _transition_tournament(
    tournament_id: int,
    allowed_from: tuple[str, ...],
    target_status: str,
    message: str,
) -> Tournament:
    """Applies one explicit tournament status transition atomically."""
    with transaction.atomic():
        tournament = Tournament.objects.select_for_update().filter(pk=tournament_id).first()
        if tournament is None:
            raise NotFoundError("Tournament not found")
        if tournament.status not in allowed_from:
            raise ConflictError(message, code="invalid_status_transition")
        tournament.status = target_status
        tournament.save(update_fields=["status", "updated_at"])
        return tournament


def open_tournament_registration(tournament_id: int) -> Tournament:
    """Moves a draft tournament into registration."""
    return _transition_tournament(
        tournament_id,
        (Tournament.Status.DRAFT,),
        Tournament.Status.REGISTRATION,
        "Only a draft tournament can open registration",
    )


def start_organizer_tournament(tournament_id: int) -> Tournament:
    """Starts a tournament that is accepting entries."""
    return _transition_tournament(
        tournament_id,
        (Tournament.Status.REGISTRATION,),
        Tournament.Status.ONGOING,
        "Only a tournament in registration can be started",
    )


def finish_organizer_tournament(tournament_id: int) -> Tournament:
    """Finishes an ongoing tournament."""
    return _transition_tournament(
        tournament_id,
        (Tournament.Status.ONGOING,),
        Tournament.Status.FINISHED,
        "Only an ongoing tournament can be finished",
    )


def delete_organizer_tournament(tournament_id: int) -> None:
    """Удаляет турнир только до появления заявок и матчей."""
    tournament = _organizer_tournament(tournament_id)
    if tournament.entries.exists() or tournament.matches.exists():
        raise ConflictError(
            "Tournament with entries or matches cannot be deleted", code="tournament_in_use"
        )
    tournament.delete()


def organizer_entries(tournament_id: int) -> list:
    """Lists entry applications with team, captain, and active roster size."""
    tournament = _organizer_tournament(tournament_id)
    return list(
        tournament.entries.select_related("team", "team__captain")
        .annotate(player_count=Count("players", filter=Q(players__status="active")))
        .order_by("submitted_at", "id")
    )
