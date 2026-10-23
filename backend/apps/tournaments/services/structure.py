from django.db import IntegrityError
from django.db.models.deletion import ProtectedError

from apps.tournaments.models import Group, Round, Stage
from config.domain_errors import DomainError
from .tournaments import get_organizer_tournament


def _organizer_stage(stage_id: int) -> Stage:
    """Loads a stage by its unique ID without requiring its parent ID in the URL."""
    stage = Stage.objects.filter(pk=stage_id).first()
    if stage is None:
        raise DomainError("Stage not found", 404)
    return stage


def list_organizer_stages(tournament_id: int) -> list[Stage]:
    """Returns ordered stages of an organizer-owned tournament."""
    tournament = get_organizer_tournament(tournament_id)
    return list(tournament.stages.order_by("ord", "id"))


def create_organizer_stage(tournament_id: int, data: dict) -> Stage:
    """Creates a stage in an organizer-owned tournament."""
    tournament = _organizer_tournament(tournament_id)
    try:
        return Stage.objects.create(tournament=tournament, **data)
    except IntegrityError as error:
        raise DomainError("Stage order is already in use", 409) from error


def update_organizer_stage(stage_id: int, data: dict) -> Stage:
    """Updates stage name, kind and order."""
    if not data:
        raise DomainError("At least one field must be provided", 422)
    stage = _organizer_stage(stage_id)
    for field, value in data.items():
        setattr(stage, field, value)
    try:
        stage.save(update_fields=list(data))
    except IntegrityError as error:
        raise DomainError("Stage order is already in use", 409) from error
    return stage


def delete_organizer_stage(stage_id: int) -> None:
    """Deletes a stage unless matches depend on it."""
    stage = _organizer_stage(stage_id)
    try:
        stage.delete()
    except ProtectedError as error:
        raise DomainError("Stage has matches and cannot be deleted", 409) from error


def list_organizer_groups(stage_id: int) -> list[Group]:
    """Returns groups for a group-format stage."""
    stage = _organizer_stage(stage_id)
    if stage.kind != Stage.Kind.GROUPS:
        raise DomainError("Groups can only be managed in a groups stage", 409)
    return list(stage.groups.order_by("ord", "id"))


def create_organizer_group(stage_id: int, data: dict) -> Group:
    """Creates a uniquely ordered group in a groups stage."""
    stage = _organizer_stage(stage_id)
    if stage.kind != Stage.Kind.GROUPS:
        raise DomainError("Groups can only be managed in a groups stage", 409)
    try:
        return Group.objects.create(stage=stage, **data)
    except IntegrityError as error:
        raise DomainError("Group order or name is already in use", 409) from error


def _organizer_group(group_id: int) -> Group:
    """Loads a group by its unique ID."""
    group = Group.objects.filter(pk=group_id).first()
    if group is None:
        raise DomainError("Group not found", 404)
    return group


def update_organizer_group(group_id: int, data: dict) -> Group:
    """Updates a group's name or order."""
    if not data:
        raise DomainError("At least one field must be provided", 422)
    group = _organizer_group(group_id)
    for field, value in data.items():
        setattr(group, field, value)
    try:
        group.save(update_fields=list(data))
    except IntegrityError as error:
        raise DomainError("Group order or name is already in use", 409) from error
    return group


def delete_organizer_group(group_id: int) -> None:
    """Deletes a group unless matches depend on it."""
    group = _organizer_group(group_id)
    try:
        group.delete()
    except ProtectedError as error:
        raise DomainError("Group has matches and cannot be deleted", 409) from error


def list_organizer_rounds(stage_id: int) -> list[Round]:
    """Returns ordered rounds for a stage."""
    return list(_organizer_stage(stage_id).rounds.order_by("ord", "id"))


def create_organizer_round(stage_id: int, data: dict) -> Round:
    """Creates a round in a stage."""
    stage = _organizer_stage(stage_id)
    try:
        return Round.objects.create(stage=stage, **data)
    except IntegrityError as error:
        raise DomainError("Round order is already in use", 409) from error


def _organizer_round(round_id: int) -> Round:
    """Loads a round by its unique ID."""
    round_obj = Round.objects.filter(pk=round_id).first()
    if round_obj is None:
        raise DomainError("Round not found", 404)
    return round_obj


def update_organizer_round(round_id: int, data: dict) -> Round:
    """Updates a round's name or order."""
    if not data:
        raise DomainError("At least one field must be provided", 422)
    round_obj = _organizer_round(round_id)
    for field, value in data.items():
        setattr(round_obj, field, value)
    try:
        round_obj.save(update_fields=list(data))
    except IntegrityError as error:
        raise DomainError("Round order is already in use", 409) from error
    return round_obj


def delete_organizer_round(round_id: int) -> None:
    """Deletes a round unless matches depend on it."""
    round_obj = _organizer_round(round_id)
    try:
        round_obj.delete()
    except ProtectedError as error:
        raise DomainError("Round has matches and cannot be deleted", 409) from error
