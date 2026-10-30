from .captain import captain_router
from .judge import judge_router
from .organizer import organizer_router
from .public import matches_router, public_router

router = public_router

__all__ = [
    "captain_router",
    "judge_router",
    "matches_router",
    "organizer_router",
    "public_router",
    "router",
]
