from typing import Literal

TournamentEntryStatus = Literal["pending", "accepted", "rejected", "withdrawn"]


TournamentStatus = Literal["draft", "registration", "ongoing", "finished"]


TournamentVisibility = Literal["public", "unlisted", "private"]


StageKind = Literal["league", "groups", "playoff"]
