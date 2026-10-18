from django.db import DatabaseError, connection
from ninja import NinjaAPI, Schema

from apps.matches.api.routes import router as matches_router
from apps.matches.api.routes import today_router, tournament_matches_router
from apps.teams.api.routes import router as teams_router
from apps.tournaments.api.routes import router as tournaments_router


class HealthResponse(Schema):
    status: str
    database: str


class LivenessResponse(Schema):
    status: str


api = NinjaAPI(
    title="Football Platform Public API",
    version="1.0.0",
    description="Public API for tournament platform.",
)


@api.get("/health/live", response=LivenessResponse, tags=["System"])
def liveness_check(request):
    """Проверяет доступность приложения"""
    return {"status": "ok"}


@api.get(
    "/health/ready",
    response={200: HealthResponse, 503: HealthResponse},
    tags=["System"],
)
def readiness_check(request):
    """Проверяет подключение приложения к базе"""
    try:
        connection.ensure_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except DatabaseError:
        return 503, {"status": "unavailable", "database": "unavailable"}
    return {"status": "ok", "database": "ok"}


api.add_router("/tournaments", tournaments_router)
api.add_router("/tournaments", tournament_matches_router)
api.add_router("/matches", matches_router)
api.add_router("", today_router)
api.add_router("", teams_router)
