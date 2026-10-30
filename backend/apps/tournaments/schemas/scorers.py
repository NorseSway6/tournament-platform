from ninja import Schema


class ScorerOut(Schema):
    """Бомбардир турнира и его команда."""

    player_id: int
    player_name: str
    team_id: int | None
    team_name: str | None
    goals: int


class ScorersOut(Schema):
    """Список бомбардиров публичного турнира."""

    tournament_id: int
    items: list[ScorerOut]
    total: int
