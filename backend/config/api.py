from functools import partial
from typing import Literal

from django.db import DatabaseError, connection
from django.http import Http404
from ninja import NinjaAPI, Schema
from ninja.errors import HttpError, ValidationError
from ninja.errors import AuthenticationError

from config.api_errors import (
    ErrorOut,
    api_response,
    handle_authentication_error,
    handle_domain_error,
    handle_http_error,
    handle_not_found,
    handle_unexpected_error,
    handle_validation_error,
)
from apps.identity_access.api.routes import router as identity_router
from apps.organizations.api.routes import router as organizations_organizer_router
from apps.matches.api.routes import router as matches_router
from apps.matches.api.routes import (
    captain_router as match_captain_router,
    judge_router,
    organizer_router as match_organizer_router,
    today_router,
    tournament_matches_router,
)
from apps.teams.api.routes import (
    captain_router as team_captain_router,
    organizer_router as team_organizer_router,
    router as teams_router,
)
from apps.teams.api.entries import router as team_entries_router
from apps.tournaments.api.routes import (
    organizer_router as tournament_organizer_router,
    router as tournaments_router,
)
from config.domain_errors import DomainError


class HealthResponse(Schema):
    status: Literal["ok"]
    database: Literal["ok"]


class LivenessResponse(Schema):
    status: Literal["ok"]


api = NinjaAPI(
    title="Football Platform Public API",
    version="1.0.0",
    description="Public API for tournament platform.",
)
api.add_exception_handler(HttpError, partial(handle_http_error, api=api))
api.add_exception_handler(DomainError, partial(handle_domain_error, api=api))
api.add_exception_handler(
    AuthenticationError, partial(handle_authentication_error, api=api)
)
api.add_exception_handler(Http404, partial(handle_not_found, api=api))
api.add_exception_handler(ValidationError, partial(handle_validation_error, api=api))
api.add_exception_handler(Exception, partial(handle_unexpected_error, api=api))


@api.get(
    "/health/live",
    response=api_response(LivenessResponse),
    tags=["System"],
    include_in_schema=False,
)
def liveness_check(request):
    """Проверяет доступность приложения"""
    return {"status": "ok"}


@api.get(
    "/health/ready",
    response=api_response({200: HealthResponse, 503: ErrorOut}),
    tags=["System"],
    include_in_schema=False,
)
def readiness_check(request):
    """Проверяет подключение приложения к базе"""
    try:
        connection.ensure_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except DatabaseError:
        return 503, {
            "code": "service_unavailable",
            "message": "Database is unavailable",
            "problems": None,
        }
    return {"status": "ok", "database": "ok"}


api.add_router("/tournaments", tournaments_router)
api.add_router("/tournaments", tournament_matches_router)
api.add_router("/matches", matches_router)
api.add_router("", judge_router)
api.add_router("", match_captain_router)
api.add_router("", team_captain_router)
api.add_router("/organizer", tournament_organizer_router)
api.add_router("/organizer", organizations_organizer_router)
api.add_router("/organizer", team_organizer_router)
api.add_router("/organizer", match_organizer_router)
api.add_router("", today_router)
api.add_router("", teams_router)
api.add_router("", team_entries_router)
api.add_router("", identity_router)
