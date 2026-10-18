from datetime import date, datetime

from ninja import Schema


class TeamSummary(Schema):
    id: int
    name: str
    city: str


class EntrySummary(Schema):
    id: int
    status: str
    team: TeamSummary


class TournamentSummary(Schema):
    id: int
    slug: str
    name: str


class StageSummary(Schema):
    id: int
    name: str
    kind: str
    ord: int


class RoundSummary(Schema):
    id: int
    name: str
    ord: int


class VenueSummary(Schema):
    id: int
    name: str
    address: str


class EventPlayerSummary(Schema):
    entry_player_id: int
    player_id: int
    name: str
    number: int

    @staticmethod
    def resolve_entry_player_id(entry_player) -> int:
        """Отдаёт ID записи игрока в составе заявки на турнир"""
        return entry_player.id

    @staticmethod
    def resolve_name(entry_player) -> str:
        """Собирает публичное имя игрока, связанного с событием"""
        player = entry_player.player
        return " ".join(
            part
            for part in (player.last_name, player.first_name, player.middle_name)
            if part
        )


class MatchEventOut(Schema):
    id: str
    seq: int
    type: str
    entry_id: int | None
    player: EventPlayerSummary | None
    minute: int | None
    second: int | None
    client_created_at: datetime | None
    created_at: datetime
    target_event_id: str | None

    @staticmethod
    def resolve_id(event) -> str:
        """Сериализует UUID события в строковый формат API"""
        return str(event.id)

    @staticmethod
    def resolve_target_event_id(event) -> str | None:
        """Сериализует UUID отменяемого или пересматриваемого события"""
        return str(event.target_event_id) if event.target_event_id else None


class MatchOut(Schema):
    id: int
    tournament: TournamentSummary
    stage: StageSummary
    round: RoundSummary | None
    home_entry: EntrySummary | None
    away_entry: EntrySummary | None
    venue: VenueSummary | None
    scheduled_at: datetime | None
    scheduled_end: datetime | None
    duration_min: int
    status: str
    result_type: str
    home_score: int | None
    away_score: int | None
    started_at: datetime | None
    finished_at: datetime | None
    confirmed_at: datetime | None


class MatchDetailOut(MatchOut):
    events: list[MatchEventOut]

    @staticmethod
    def resolve_events(match) -> list:
        """Возвращает ленту событий, предзагруженную selector-ом матча"""
        return match.public_events


class MatchPage(Schema):
    items: list[MatchOut]
    total: int
    page: int
    page_size: int


class TodayOut(Schema):
    date: date
    items: list[MatchOut]
    total: int
