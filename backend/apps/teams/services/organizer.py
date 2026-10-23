from django.db import transaction

from apps.teams.models import TournamentEntry
from apps.tournaments.models import Tournament

from config.domain_errors import DomainError


def decide_organizer_entry(
    entry_id: int, status: str, decision_comment: str = ""
) -> TournamentEntry:
    """Applies an organizer's decision to a pending tournament entry."""
    if status not in (TournamentEntry.Status.ACCEPTED, TournamentEntry.Status.REJECTED):
        raise DomainError("Entry decision must be accepted or rejected", 422)
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
                raise DomainError("Entry not found", 404)
        if entry.status == status:
            return entry
        if entry.status != TournamentEntry.Status.PENDING:
            raise DomainError("Only pending entries can be decided", 409)
        if entry.tournament.status not in (
            Tournament.Status.REGISTRATION,
            Tournament.Status.ONGOING,
        ):
            raise DomainError(
                "Entries cannot be decided for this tournament", 409
            )
        entry.status = status
        entry.decision_comment = decision_comment.strip()
        entry.save(update_fields=["status", "decision_comment"])
        return entry


