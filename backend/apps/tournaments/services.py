from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.db.models.deletion import ProtectedError
from django.core.exceptions import ValidationError

from apps.organizations.models import Organization
from apps.tournaments.models import Group, Round, Stage, Tournament


class OrganizerTournamentError(Exception):
    """Сообщает об ошибке операции организатора с турниром."""

    def __init__(self, message: str, status_code: int = 409):
        super().__init__(message)
        self.status_code = status_code


def _validate_dates(data: dict) -> None:
    """Проверяет порядок дат турнира до сохранения."""
    starts_on = data.get("starts_on")
    ends_on = data.get("ends_on")
    if starts_on and ends_on and ends_on < starts_on:
        raise OrganizerTournamentError("ends_on must be on or after starts_on", 422)


def _validate_regulation(regulation: dict) -> None:
    """Проверяет поддерживаемую сейчас часть регламента таблицы."""
    if not isinstance(regulation, dict):
        raise OrganizerTournamentError("regulation must be an object", 422)
    standings = regulation.get("standings")
    if standings is None:
        return
    if not isinstance(standings, dict):
        raise OrganizerTournamentError("regulation.standings must be an object", 422)
    for key in ("points_for_win", "points_for_draw", "points_for_loss"):
        if key in standings and (
            not isinstance(standings[key], int)
            or isinstance(standings[key], bool)
            or standings[key] < 0
        ):
            raise OrganizerTournamentError(f"{key} must be a non-negative integer", 422)
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
        raise OrganizerTournamentError("tie_breakers contains an unsupported value", 422)


def _organizer_tournament(tournament_id: int) -> Tournament:
    """Находит турнир по ID; authorization scope will be added with identity access."""
    tournament = Tournament.objects.filter(pk=tournament_id).first()
    if tournament is None:
        raise OrganizerTournamentError("Tournament not found", 404)
    return tournament


def list_organizer_tournaments(organization_id: int) -> list[Tournament]:
    """Returns tournaments for the organization selected by the caller."""
    if not Organization.objects.filter(pk=organization_id).exists():
        raise OrganizerTournamentError("Organization not found", 404)
    return list(Tournament.objects.filter(organization_id=organization_id).order_by("id"))


def get_organizer_tournament(tournament_id: int) -> Tournament:
    """Возвращает подробности турнира во временной области организатора."""
    return _organizer_tournament(tournament_id)


def create_organizer_tournament(data: dict) -> Tournament:
    """Создаёт турнир в организации, явно выбранной клиентом."""
    _validate_dates(data)
    _validate_regulation(data.get("regulation", {}))
    organization_id = data.pop("organization_id", None)
    organization = Organization.objects.filter(pk=organization_id).first()
    if organization is None:
        raise OrganizerTournamentError("Organization not found", 404)
    try:
        with transaction.atomic():
            tournament = Tournament(organization=organization, **data)
            tournament.full_clean()
            tournament.save()
            return tournament
    except ValidationError as error:
        raise OrganizerTournamentError(str(error), 422) from error
    except IntegrityError as error:
        raise OrganizerTournamentError("Tournament slug already exists for this organization", 409) from error


def update_organizer_tournament(tournament_id: int, data: dict) -> Tournament:
    """Partially updates tournament fields while retaining its organization."""
    if not data:
        raise OrganizerTournamentError("At least one field must be provided", 422)
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
        raise OrganizerTournamentError(str(error), 422) from error
    except IntegrityError as error:
        raise OrganizerTournamentError("Tournament slug already exists for this organization", 409) from error


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
        raise OrganizerTournamentError("Tournament with entries or matches cannot be deleted", 409)
    tournament.delete()


def organizer_entries(tournament_id: int) -> list:
    """Lists entry applications with team, captain, and active roster size."""
    tournament = _organizer_tournament(tournament_id)
    return list(
        tournament.entries.select_related("team", "team__captain")
        .annotate(player_count=Count("players", filter=Q(players__status="active")))
        .order_by("submitted_at", "id")
    )


def _organizer_stage(stage_id: int) -> Stage:
    """Loads a stage by its unique ID without requiring its parent ID in the URL."""
    stage = Stage.objects.filter(pk=stage_id).first()
    if stage is None:
        raise OrganizerTournamentError("Stage not found", 404)
    return stage


def list_organizer_stages(tournament_id: int) -> list[Stage]:
    """Returns ordered stages of an organizer-owned tournament."""
    tournament = _organizer_tournament(tournament_id)
    return list(tournament.stages.order_by("ord", "id"))


def create_organizer_stage(tournament_id: int, data: dict) -> Stage:
    """Creates a stage in an organizer-owned tournament."""
    tournament = _organizer_tournament(tournament_id)
    try:
        return Stage.objects.create(tournament=tournament, **data)
    except IntegrityError as error:
        raise OrganizerTournamentError("Stage order is already in use", 409) from error


def update_organizer_stage(stage_id: int, data: dict) -> Stage:
    """Updates stage name, kind and order."""
    if not data:
        raise OrganizerTournamentError("At least one field must be provided", 422)
    stage = _organizer_stage(stage_id)
    for field, value in data.items():
        setattr(stage, field, value)
    try:
        stage.save(update_fields=list(data))
    except IntegrityError as error:
        raise OrganizerTournamentError("Stage order is already in use", 409) from error
    return stage


def delete_organizer_stage(stage_id: int) -> None:
    """Deletes a stage unless matches depend on it."""
    stage = _organizer_stage(stage_id)
    try:
        stage.delete()
    except ProtectedError as error:
        raise OrganizerTournamentError("Stage has matches and cannot be deleted", 409) from error


def list_organizer_groups(stage_id: int) -> list[Group]:
    """Returns groups for a group-format stage."""
    stage = _organizer_stage(stage_id)
    if stage.kind != Stage.Kind.GROUPS:
        raise OrganizerTournamentError("Groups can only be managed in a groups stage", 409)
    return list(stage.groups.order_by("ord", "id"))


def create_organizer_group(stage_id: int, data: dict) -> Group:
    """Creates a uniquely ordered group in a groups stage."""
    stage = _organizer_stage(stage_id)
    if stage.kind != Stage.Kind.GROUPS:
        raise OrganizerTournamentError("Groups can only be managed in a groups stage", 409)
    try:
        return Group.objects.create(stage=stage, **data)
    except IntegrityError as error:
        raise OrganizerTournamentError("Group order or name is already in use", 409) from error


def _organizer_group(group_id: int) -> Group:
    """Loads a group by its unique ID."""
    group = Group.objects.filter(pk=group_id).first()
    if group is None:
        raise OrganizerTournamentError("Group not found", 404)
    return group


def update_organizer_group(group_id: int, data: dict) -> Group:
    """Updates a group's name or order."""
    if not data:
        raise OrganizerTournamentError("At least one field must be provided", 422)
    group = _organizer_group(group_id)
    for field, value in data.items():
        setattr(group, field, value)
    try:
        group.save(update_fields=list(data))
    except IntegrityError as error:
        raise OrganizerTournamentError("Group order or name is already in use", 409) from error
    return group


def delete_organizer_group(group_id: int) -> None:
    """Deletes a group unless matches depend on it."""
    group = _organizer_group(group_id)
    try:
        group.delete()
    except ProtectedError as error:
        raise OrganizerTournamentError("Group has matches and cannot be deleted", 409) from error


def list_organizer_rounds(stage_id: int) -> list[Round]:
    """Returns ordered rounds for a stage."""
    return list(_organizer_stage(stage_id).rounds.order_by("ord", "id"))


def create_organizer_round(stage_id: int, data: dict) -> Round:
    """Creates a round in a stage."""
    stage = _organizer_stage(stage_id)
    try:
        return Round.objects.create(stage=stage, **data)
    except IntegrityError as error:
        raise OrganizerTournamentError("Round order is already in use", 409) from error


def _organizer_round(round_id: int) -> Round:
    """Loads a round by its unique ID."""
    round_obj = Round.objects.filter(pk=round_id).first()
    if round_obj is None:
        raise OrganizerTournamentError("Round not found", 404)
    return round_obj


def update_organizer_round(round_id: int, data: dict) -> Round:
    """Updates a round's name or order."""
    if not data:
        raise OrganizerTournamentError("At least one field must be provided", 422)
    round_obj = _organizer_round(round_id)
    for field, value in data.items():
        setattr(round_obj, field, value)
    try:
        round_obj.save(update_fields=list(data))
    except IntegrityError as error:
        raise OrganizerTournamentError("Round order is already in use", 409) from error
    return round_obj


def delete_organizer_round(round_id: int) -> None:
    """Deletes a round unless matches depend on it."""
    round_obj = _organizer_round(round_id)
    try:
        round_obj.delete()
    except ProtectedError as error:
        raise OrganizerTournamentError("Round has matches and cannot be deleted", 409) from error
