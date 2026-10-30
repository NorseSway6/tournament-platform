from .organizer import organizer_router
from .public import public_router

router = public_router

__all__ = [
    "organizer_router",
    "public_router",
    "router",
]
