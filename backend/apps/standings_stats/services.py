from dataclasses import dataclass
from typing import Any

from apps.matches.models import Match
from apps.standings_stats.selectors import (
    accepted_entries,
    completed_stage_matches,
    tournament_stages,
)
from apps.teams.models import TournamentEntry
from apps.tournaments.models import GroupEntry, Stage, Tournament

DEFAULT_RULES = {
    "points_for_win": 3,
    "points_for_draw": 1,
    "points_for_loss": 0,
    "tie_breakers": ["points", "goal_difference", "goals_for", "team_name", "team_id"],
}
ALLOWED_TIE_BREAKERS = {
    "points",
    "goal_difference",
    "goals_for",
    "team_name",
    "team_id",
}


@dataclass
class EntryStanding:
    entry: TournamentEntry
    played: int = 0
    wins: int = 0
    draws: int = 0
    losses: int = 0
    goals_for: int = 0
    goals_against: int = 0
    points: int = 0

    @property
    def goal_difference(self) -> int:
        """Вычисляет разницу забитых и пропущенных голов"""
        return self.goals_for - self.goals_against


def _rules_for(tournament: Tournament) -> dict[str, Any]:
    """Читает правила таблицы из регламента с безопасными значениями MVP"""
    regulation = tournament.regulation if isinstance(tournament.regulation, dict) else {}
    configured = regulation.get("standings", {})
    if not isinstance(configured, dict):
        configured = {}
    rules = {**DEFAULT_RULES, **configured}
    for points_field in ("points_for_win", "points_for_draw", "points_for_loss"):
        value = rules[points_field]
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            rules[points_field] = DEFAULT_RULES[points_field]
    tie_breakers = rules.get("tie_breakers", DEFAULT_RULES["tie_breakers"])
    if not isinstance(tie_breakers, list) or any(
        item not in ALLOWED_TIE_BREAKERS for item in tie_breakers
    ):
        tie_breakers = DEFAULT_RULES["tie_breakers"]
    if "team_id" not in tie_breakers:
        tie_breakers = [*tie_breakers, "team_id"]
    rules["tie_breakers"] = tie_breakers
    return rules


def _add_match_result(
    home: EntryStanding, away: EntryStanding, match: Match, rules: dict[str, Any]
) -> None:
    """Учитывает результат одного матча в показателях обеих команд"""
    home.played += 1
    away.played += 1
    home.goals_for += match.home_score
    home.goals_against += match.away_score
    away.goals_for += match.away_score
    away.goals_against += match.home_score

    if match.home_score > match.away_score:
        home.wins += 1
        away.losses += 1
        home.points += rules["points_for_win"]
        away.points += rules["points_for_loss"]
    elif match.home_score < match.away_score:
        away.wins += 1
        home.losses += 1
        away.points += rules["points_for_win"]
        home.points += rules["points_for_loss"]
    else:
        home.draws += 1
        away.draws += 1
        home.points += rules["points_for_draw"]
        away.points += rules["points_for_draw"]


def _sort_key(standing: EntryStanding, tie_breakers: list[str]) -> tuple[Any, ...]:
    """Строит ключ сортировки, включая стабильный финальный ID команды"""
    values = {
        "points": standing.points,
        "goal_difference": standing.goal_difference,
        "goals_for": standing.goals_for,
        "team_name": standing.entry.team.name.casefold(),
        "team_id": standing.entry.team_id,
    }
    descending = {"points", "goal_difference", "goals_for"}
    return tuple(-values[key] if key in descending else values[key] for key in tie_breakers)


def _standings_for_stage(
    entries: list[TournamentEntry], matches: list[Match], rules: dict[str, Any]
) -> list[dict[str, Any]]:
    """Рассчитывает и сортирует строки таблицы для одного этапа"""
    standings = {entry.id: EntryStanding(entry=entry) for entry in entries}
    for match in matches:
        home = standings.get(match.home_entry_id)
        away = standings.get(match.away_entry_id)
        if home is None or away is None or match.home_score is None or match.away_score is None:
            continue
        _add_match_result(home, away, match, rules)

    ordered = sorted(standings.values(), key=lambda row: _sort_key(row, rules["tie_breakers"]))
    return [
        {
            "position": position,
            "entry_id": row.entry.id,
            "team_id": row.entry.team_id,
            "team_name": row.entry.team.name,
            "played": row.played,
            "wins": row.wins,
            "draws": row.draws,
            "losses": row.losses,
            "goals_for": row.goals_for,
            "goals_against": row.goals_against,
            "goal_difference": row.goal_difference,
            "points": row.points,
        }
        for position, row in enumerate(ordered, start=1)
    ]


def calculate_tournament_standings(tournament: Tournament) -> dict[str, Any]:
    """Рассчитывает отдельные таблицы для этапов лиги и групп турнира"""
    entries = list(accepted_entries(tournament))
    matches_by_stage: dict[int, list[Match]] = {}
    for match in completed_stage_matches(tournament):
        matches_by_stage.setdefault(match.stage_id, []).append(match)
    fixture_entry_ids: dict[int, set[int]] = {}
    for match in Match.objects.filter(tournament=tournament, group__isnull=False).values_list(
        "group_id", "home_entry_id", "away_entry_id"
    ):
        fixture_entry_ids.setdefault(match[0], set()).update(
            entry_id for entry_id in match[1:] if entry_id is not None
        )
    group_entry_ids: dict[int, set[int]] = {}
    for group_id, entry_id in GroupEntry.objects.filter(
        group__stage__tournament=tournament
    ).values_list("group_id", "entry_id"):
        group_entry_ids.setdefault(group_id, set()).add(entry_id)

    rules = _rules_for(tournament)
    stages = []
    for stage in tournament_stages(tournament):
        if stage.kind not in (Stage.Kind.LEAGUE, Stage.Kind.GROUPS):
            continue
        stage_matches = matches_by_stage.get(stage.id, [])
        groups = []
        if stage.kind == Stage.Kind.GROUPS:
            for group in stage.groups.order_by("ord", "id"):
                group_matches = [match for match in stage_matches if match.group_id == group.id]
                # Explicit assignments are authoritative; fixtures remain a fallback
                # for groups created before GroupEntry existed.
                entry_ids = group_entry_ids.get(group.id, fixture_entry_ids.get(group.id, set()))
                group_entries = [entry for entry in entries if entry.id in entry_ids]
                groups.append(
                    {
                        "group_id": group.id,
                        "group_name": group.name,
                        "items": _standings_for_stage(group_entries, group_matches, rules),
                    }
                )
            items = []
        else:
            items = _standings_for_stage(entries, stage_matches, rules)
        stages.append(
            {
                "stage_id": stage.id,
                "stage_name": stage.name,
                "stage_kind": stage.kind,
                "items": items,
                "groups": groups,
            }
        )
    return {"tournament_id": tournament.id, "stages": stages, "rules": rules}
