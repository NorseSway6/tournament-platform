from django.db import transaction

from apps.identity_access.models import User
from apps.identity_access.selectors import get_active_user_by_identifier
from apps.teams.models import Team
from config.domain_errors import (
    ConflictError,
    DomainValidationError,
    ForbiddenError,
    NotFoundError,
    ServiceUnavailableError,
)


def create_captain_team(captain_id: int, data: dict) -> Team:
    """Создаёт команду, назначая владельцем аутентифицированного капитана."""
    if not User.objects.filter(pk=captain_id).exists():
        raise ServiceUnavailableError("The authenticated captain account does not exist")
    name = data["name"].strip()
    if not name:
        raise DomainValidationError("Team name cannot be empty")
    return Team.objects.create(
        name=name,
        city=data.get("city", "").strip(),
        captain_id=captain_id,
    )


def list_captain_teams(captain_id: int) -> list[Team]:
    """Возвращает команды капитана вместе с публичными заявками."""
    return list(
        Team.objects.filter(captain_id=captain_id)
        .prefetch_related("entries__tournament")
        .order_by("name", "id")
    )


def transfer_captain_team(captain_id: int, team_id: int, identifier: str) -> Team:
    """Передаёт капитанство команды другому активному пользователю."""
    with transaction.atomic():
        team = Team.objects.select_for_update().select_related("captain").filter(pk=team_id).first()
        if team is None:
            raise NotFoundError("Team not found")
        if team.captain_id != captain_id:
            raise ForbiddenError("Only the current captain can transfer the team")
        new_captain = get_active_user_by_identifier(identifier)
        if new_captain is None:
            raise NotFoundError("Active user not found")
        if team.captain_id == new_captain.pk:
            raise ConflictError("User is already the team captain", code="already_captain")
        team.captain = new_captain
        team.save(update_fields=["captain", "updated_at"])
    return team


def update_captain_team(captain_id: int, team_id: int, changes: dict) -> Team:
    """Изменяет название и город команды, принадлежащей капитану."""
    team = Team.objects.filter(pk=team_id, captain_id=captain_id).first()
    if team is None:
        if not Team.objects.filter(pk=team_id).exists():
            raise NotFoundError("Team not found")
        raise ForbiddenError("The authenticated captain does not own this team")
    if not changes:
        raise DomainValidationError("At least one field must be provided")
    if "name" in changes:
        name = changes["name"].strip()
        if not name:
            raise DomainValidationError("Team name cannot be empty")
        team.name = name
    if "city" in changes:
        team.city = (changes["city"] or "").strip()
    team.save(update_fields=["name", "city", "updated_at"])
    return team
