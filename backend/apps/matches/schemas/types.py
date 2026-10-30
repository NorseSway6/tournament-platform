from typing import Literal

MatchStatus = Literal[
    "scheduled",
    "lineups_open",
    "live",
    "finished",
    "confirmed",
    "postponed",
    "cancelled",
    "technical",
]


MatchResultType = Literal["played", "tech_win_home", "tech_win_away", "walkover"]

TechnicalResultType = Literal["tech_win_home", "tech_win_away", "walkover"]


MatchEventType = Literal[
    "goal",
    "own_goal",
    "yellow",
    "red",
    "sub",
    "period_start",
    "period_end",
    "pause",
    "resume",
    "finish",
    "void",
    "review_ok",
    "note",
]


LineupStatus = Literal["draft", "submitted", "accepted", "rejected"]


LineupPlayerRole = Literal["player", "captain"]


OfficialRole = Literal["referee", "assistant_referee", "fourth_official", "delegate"]


StageKind = Literal["league", "groups", "playoff"]


EntryStatus = Literal["pending", "accepted", "rejected", "withdrawn"]


EventPeriod = Literal[
    "first_half",
    "half_time",
    "second_half",
    "extra_time_first",
    "extra_time_second",
    "penalties",
]


EventSource = Literal["judge", "organizer", "system"]
