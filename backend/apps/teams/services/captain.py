from apps.identity_access.models import User
from apps.teams.models import Team

from config.domain_errors import DomainError


def create_captain_team(captain_id: int, data: dict) -> Team:
    """Создаёт команду, назначая владельцем аутентифицированного капитана."""
    if not User.objects.filter(pk=captain_id).exists():
        raise DomainError(
            "The authenticated captain account does not exist", 503
        )
    name = data["name"].strip()
    if not name:
        raise DomainError("Team name cannot be empty", 422)
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


def update_captain_team(captain_id: int, team_id: int, changes: dict) -> Team:
    """Изменяет название и город команды, принадлежащей капитану."""
    team = Team.objects.filter(pk=team_id, captain_id=captain_id).first()
    if team is None:
        if not Team.objects.filter(pk=team_id).exists():
            raise DomainError("Team not found", 404)
        raise DomainError("The authenticated captain does not own this team", 403)
    if not changes:
        raise DomainError("At least one field must be provided", 422)
    if "name" in changes:
        name = changes["name"].strip()
        if not name:
            raise DomainError("Team name cannot be empty", 422)
        team.name = name
    if "city" in changes:
        team.city = (changes["city"] or "").strip()
    team.save(update_fields=["name", "city", "updated_at"])
    return team


