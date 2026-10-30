from ninja import Schema

from apps.matches.schemas.types import EntryStatus, StageKind


class TeamSummary(Schema):
    """Краткие публичные данные команды в составе матча."""

    id: int
    name: str
    city: str


class EntrySummary(Schema):
    """Заявка команды на турнир, участвующая в матче."""

    id: int
    status: EntryStatus
    team: TeamSummary


class TournamentSummary(Schema):
    """Краткая информация о турнире и его часовом поясе."""

    id: int
    slug: str
    name: str
    timezone: str

    @staticmethod
    def resolve_timezone(tournament) -> str:
        """Возвращает часовой пояс, настроенный для организации, проводящей турнир."""
        return tournament.organization.timezone


class MatchStageSummary(Schema):
    """Этап турнира, к которому относится матч."""

    id: int
    name: str
    kind: StageKind
    ord: int


class RoundSummary(Schema):
    """Тур турнира в карточке матча."""

    id: int
    name: str
    ord: int


class GroupSummary(Schema):
    """Группа этапа, к которой относится матч."""

    id: int
    name: str
    ord: int


class VenueSummary(Schema):
    """Краткие данные площадки проведения матча."""

    id: int
    name: str
    address: str
