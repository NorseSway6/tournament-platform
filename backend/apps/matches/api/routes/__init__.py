from .captain import captain_router
from .judge import judge_router
from .organizer import organizer_router
from .public import public_router

router = public_router

__all__ = [
    "captain_router",
    "judge_router",
    "organizer_router",
    "public_router",
    "router",
]
