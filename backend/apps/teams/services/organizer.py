from django.db import transaction

from apps.common.errors import ConflictError, DomainValidationError, NotFoundError
from apps.teams.models import TournamentEntry
from apps.tournaments.models import Tournament


def decide_organizer_entry(
    entry_id: int, status: str, decision_comment: str = ""
) -> TournamentEntry:
    """Применяет решение организатора к ожидающей рассмотрения заявке на участие в турнире."""
    if status not in (TournamentEntry.Status.ACCEPTED, TournamentEntry.Status.REJECTED):
        raise DomainValidationError("Entry decision must be accepted or rejected")
    with transaction.atomic():
        entry = (
            TournamentEntry.objects.select_for_update()
            .select_related("tournament")
            .filter(pk=entry_id)
            .first()
        )
        if entry is None:
            exists = TournamentEntry.objects.filter(pk=entry_id).exists()
            if not exists:
                raise NotFoundError("Entry not found")
        if entry.status == status:
            return entry
        if entry.status != TournamentEntry.Status.PENDING:
            raise ConflictError("Only pending entries can be decided", code="entry_not_pending")
        if entry.tournament.status not in (
            Tournament.Status.REGISTRATION,
            Tournament.Status.ONGOING,
        ):
            raise ConflictError(
                "Entries cannot be decided for this tournament", code="entry_decision_closed"
            )
        entry.status = status
        entry.decision_comment = decision_comment.strip()
        entry.save(update_fields=["status", "decision_comment"])
        return entry
