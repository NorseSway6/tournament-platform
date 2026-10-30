from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError

from apps.common.errors import ConflictError, DomainValidationError, NotFoundError
from apps.teams.models import TournamentEntry
from apps.tournaments.models import Group, GroupEntry, Round, Stage

from .tournaments import _organizer_tournament, get_organizer_tournament


def _organizer_stage(stage_id: int) -> Stage:
    """Загружает этап по его ID, указывать родительское ID в URL при этом не требуется."""
    stage = Stage.objects.filter(pk=stage_id).first()
    if stage is None:
        raise NotFoundError("Stage not found")
    return stage


def list_organizer_stages(tournament_id: int) -> list[Stage]:
    """Возвращает упорядоченные этапы турнира, принадлежащего организатору."""
    tournament = get_organizer_tournament(tournament_id)
    return list(tournament.stages.order_by("ord", "id"))


def create_organizer_stage(tournament_id: int, data: dict) -> Stage:
    """Создаёт этап в турнире, принадлежащем организатору."""
    tournament = _organizer_tournament(tournament_id)
    try:
        return Stage.objects.create(tournament=tournament, **data)
    except IntegrityError as error:
        raise ConflictError("Stage order is already in use", code="stage_order_taken") from error


def update_organizer_stage(stage_id: int, data: dict) -> Stage:
    """Обновляет название этапа, его тип и порядок."""
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
    """Удаляет этап, если только от него не зависят какие-либо сопоставления."""
    stage = _organizer_stage(stage_id)
    try:
        stage.delete()
    except ProtectedError as error:
        raise ConflictError(
            "Stage has matches and cannot be deleted", code="stage_has_matches"
        ) from error


def list_organizer_groups(stage_id: int) -> list[Group]:
    """Возвращает группы для этапа в групповом формате."""
    stage = _organizer_stage(stage_id)
    if stage.kind != Stage.Kind.GROUPS:
        raise ConflictError("Groups can only be managed in a groups stage", code="not_groups_stage")
    return list(stage.groups.order_by("ord", "id"))


def create_organizer_group(stage_id: int, data: dict) -> Group:
    """Создаёт в рамках группового этапа группу с уникальным порядком элементов."""
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
    """Загружает группу по её ID."""
    group = Group.objects.filter(pk=group_id).first()
    if group is None:
        raise NotFoundError("Group not found")
    return group


def update_organizer_group(group_id: int, data: dict) -> Group:
    """Обновляет название или порядок группы."""
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
    """Удаляет группу, если только от неё не зависят какие-либо сопоставления."""
    group = _organizer_group(group_id)
    try:
        group.delete()
    except ProtectedError as error:
        raise ConflictError(
            "Group has matches and cannot be deleted", code="group_has_matches"
        ) from error


def list_organizer_group_entries(group_id: int) -> list[GroupEntry]:
    """Возвращает явно назначенные принятые записи для группы."""
    group = _organizer_group(group_id)
    if group.stage.kind != Stage.Kind.GROUPS:
        raise ConflictError("Groups can only be managed in a groups stage", code="not_groups_stage")
    return list(
        GroupEntry.objects.filter(group=group)
        .select_related("entry__team")
        .order_by("entry__team__name", "entry_id")
    )


def replace_organizer_group_entries(group_id: int, entry_ids: list[int]) -> list[GroupEntry]:
    """Заменяет все назначения групп после проверки записей и этапа."""
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
    """Возвращает упорядоченные раунды для этапа."""
    return list(_organizer_stage(stage_id).rounds.order_by("ord", "id"))


def create_organizer_round(stage_id: int, data: dict) -> Round:
    """Создаёт раунд в этапе."""
    stage = _organizer_stage(stage_id)
    try:
        return Round.objects.create(stage=stage, **data)
    except IntegrityError as error:
        raise ConflictError("Round order is already in use", code="round_order_taken") from error


def _organizer_round(round_id: int) -> Round:
    """Загружает раунд по его уникальному ID."""
    round_obj = Round.objects.filter(pk=round_id).first()
    if round_obj is None:
        raise NotFoundError("Round not found")
    return round_obj


def update_organizer_round(round_id: int, data: dict) -> Round:
    """Обновляет название или порядок раунда."""
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
    """Удаляет раунд, если от него не зависят матчи."""
    round_obj = _organizer_round(round_id)
    try:
        round_obj.delete()
    except ProtectedError as error:
        raise ConflictError(
            "Round has matches and cannot be deleted", code="round_has_matches"
        ) from error
