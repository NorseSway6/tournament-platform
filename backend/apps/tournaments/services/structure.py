from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError

from apps.teams.models import TournamentEntry
from apps.tournaments.models import Group, GroupEntry, Round, Stage
from config.domain_errors import ConflictError, DomainValidationError, NotFoundError

from .tournaments import _organizer_tournament, get_organizer_tournament


def _organizer_stage(stage_id: int) -> Stage:
    """Loads a stage by its unique ID without requiring its parent ID in the URL."""
    stage = Stage.objects.filter(pk=stage_id).first()
    if stage is None:
        raise NotFoundError("Stage not found")
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
        raise ConflictError("Stage order is already in use", code="stage_order_taken") from error


def update_organizer_stage(stage_id: int, data: dict) -> Stage:
    """Updates stage name, kind and order."""
    if not data:
        raise DomainValidationError("At least one field must be provided")
    stage = _organizer_stage(stage_id)
    for field, value in data.items():
        setattr(stage, field, value)
    try:
        stage.save(update_fields=list(data))
    except IntegrityError as error:
        raise ConflictError("Stage order is already in use", code="stage_order_taken") from error
    return stage


def delete_organizer_stage(stage_id: int) -> None:
    """Deletes a stage unless matches depend on it."""
    stage = _organizer_stage(stage_id)
    try:
        stage.delete()
    except ProtectedError as error:
        raise ConflictError(
            "Stage has matches and cannot be deleted", code="stage_has_matches"
        ) from error


def list_organizer_groups(stage_id: int) -> list[Group]:
    """Returns groups for a group-format stage."""
    stage = _organizer_stage(stage_id)
    if stage.kind != Stage.Kind.GROUPS:
        raise ConflictError("Groups can only be managed in a groups stage", code="not_groups_stage")
    return list(stage.groups.order_by("ord", "id"))


def create_organizer_group(stage_id: int, data: dict) -> Group:
    """Creates a uniquely ordered group in a groups stage."""
    stage = _organizer_stage(stage_id)
    if stage.kind != Stage.Kind.GROUPS:
        raise ConflictError("Groups can only be managed in a groups stage", code="not_groups_stage")
    try:
        return Group.objects.create(stage=stage, **data)
    except IntegrityError as error:
        raise ConflictError(
            "Group order or name is already in use", code="group_conflict"
        ) from error


def _organizer_group(group_id: int) -> Group:
    """Loads a group by its unique ID."""
    group = Group.objects.filter(pk=group_id).first()
    if group is None:
        raise NotFoundError("Group not found")
    return group


def update_organizer_group(group_id: int, data: dict) -> Group:
    """Updates a group's name or order."""
    if not data:
        raise DomainValidationError("At least one field must be provided")
    group = _organizer_group(group_id)
    for field, value in data.items():
        setattr(group, field, value)
    try:
        group.save(update_fields=list(data))
    except IntegrityError as error:
        raise ConflictError(
            "Group order or name is already in use", code="group_conflict"
        ) from error
    return group


def delete_organizer_group(group_id: int) -> None:
    """Deletes a group unless matches depend on it."""
    group = _organizer_group(group_id)
    try:
        group.delete()
    except ProtectedError as error:
        raise ConflictError(
            "Group has matches and cannot be deleted", code="group_has_matches"
        ) from error


def list_organizer_group_entries(group_id: int) -> list[GroupEntry]:
    """Returns explicitly assigned accepted entries for a group."""
    group = _organizer_group(group_id)
    if group.stage.kind != Stage.Kind.GROUPS:
        raise ConflictError("Groups can only be managed in a groups stage", code="not_groups_stage")
    return list(
        GroupEntry.objects.filter(group=group)
        .select_related("entry__team")
        .order_by("entry__team__name", "entry_id")
    )


def replace_organizer_group_entries(group_id: int, entry_ids: list[int]) -> list[GroupEntry]:
    """Replaces all group assignments after validating entries and the stage."""
    group = _organizer_group(group_id)
    if group.stage.kind != Stage.Kind.GROUPS:
        raise ConflictError("Groups can only be managed in a groups stage", code="not_groups_stage")
    unique_ids = list(dict.fromkeys(entry_ids))
    if len(unique_ids) != len(entry_ids):
        raise DomainValidationError("An entry can only be assigned once per group")
    entries = {
        entry.id: entry
        for entry in TournamentEntry.objects.filter(
            pk__in=unique_ids,
            tournament=group.stage.tournament,
            status=TournamentEntry.Status.ACCEPTED,
        )
    }
    if len(entries) != len(unique_ids):
        raise DomainValidationError("Every entry must be accepted in the group's tournament")
    if (
        GroupEntry.objects.filter(entry_id__in=unique_ids, group__stage=group.stage)
        .exclude(group=group)
        .exists()
    ):
        raise ConflictError(
            "An entry is already assigned to another group of this stage",
            code="entry_already_in_group",
        )
    with transaction.atomic():
        GroupEntry.objects.filter(group=group).delete()
        GroupEntry.objects.bulk_create(
            [GroupEntry(group=group, entry=entry) for entry in entries.values()]
        )
    return list_organizer_group_entries(group_id)


def list_organizer_rounds(stage_id: int) -> list[Round]:
    """Returns ordered rounds for a stage."""
    return list(_organizer_stage(stage_id).rounds.order_by("ord", "id"))


def create_organizer_round(stage_id: int, data: dict) -> Round:
    """Creates a round in a stage."""
    stage = _organizer_stage(stage_id)
    try:
        return Round.objects.create(stage=stage, **data)
    except IntegrityError as error:
        raise ConflictError("Round order is already in use", code="round_order_taken") from error


def _organizer_round(round_id: int) -> Round:
    """Loads a round by its unique ID."""
    round_obj = Round.objects.filter(pk=round_id).first()
    if round_obj is None:
        raise NotFoundError("Round not found")
    return round_obj


def update_organizer_round(round_id: int, data: dict) -> Round:
    """Updates a round's name or order."""
    if not data:
        raise DomainValidationError("At least one field must be provided")
    round_obj = _organizer_round(round_id)
    for field, value in data.items():
        setattr(round_obj, field, value)
    try:
        round_obj.save(update_fields=list(data))
    except IntegrityError as error:
        raise ConflictError("Round order is already in use", code="round_order_taken") from error
    return round_obj


def delete_organizer_round(round_id: int) -> None:
    """Deletes a round unless matches depend on it."""
    round_obj = _organizer_round(round_id)
    try:
        round_obj.delete()
    except ProtectedError as error:
        raise ConflictError(
            "Round has matches and cannot be deleted", code="round_has_matches"
        ) from error
