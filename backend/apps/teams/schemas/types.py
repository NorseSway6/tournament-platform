from typing import Literal


TournamentStatus = Literal["draft", "registration", "ongoing", "finished"]


TournamentEntryStatus = Literal["pending", "accepted", "rejected", "withdrawn"]


EntryPlayerStatus = Literal["active", "removed"]
