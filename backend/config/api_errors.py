import logging
from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404, HttpRequest, HttpResponse
from ninja import Schema
from ninja.errors import AuthenticationError, HttpError, ValidationError

from config.domain_errors import DomainError


logger = logging.getLogger(__name__)


class ErrorProblem(Schema):
    """Описывает отдельное поле или параметр, не прошедший проверку."""

    location: list[str | int]
    message: str
    code: str


class ErrorOut(Schema):
    """Единый контракт ответа API на ошибки."""

    code: str
    message: str
    problems: list[ErrorProblem] | None = None


class ApiHttpError(HttpError):
    """HTTP error carrying field-level details through the shared handler."""

    def __init__(self, status_code: int, message: str, problems=None):
        super().__init__(status_code, message)
        self.problems = problems


def django_validation_problems(
    error: DjangoValidationError, location: tuple[str | int, ...] = ("body",)
) -> list[dict]:
    """Flattens Django model validation into the public ErrorOut problems shape."""
    if hasattr(error, "error_dict"):
        field_errors = error.error_dict.items()
    else:
        field_errors = ((None, error.error_list),)
    problems = []
    for field, errors in field_errors:
        for item in errors:
            for message in item.messages:
                problems.append(
                    {
                        "location": [*location, *([field] if field else [])],
                        "message": message,
                        "code": item.code or "invalid",
                    }
                )
    return problems


def handle_domain_error(
    request: HttpRequest, error: DomainError, *, api: Any
) -> HttpResponse:
    """Преобразует ожидаемую ошибку бизнес-операции в единый ErrorOut."""
    problems = getattr(error, "problems", None)
    validation_error = getattr(error, "validation_error", None)
    if problems is None and validation_error is not None:
        problems = django_validation_problems(
            validation_error,
            tuple(getattr(error, "validation_location", ("body",))),
        )
    status = error.status_code
    return api.create_response(
        request,
        {
            "code": _error_code(status),
            "message": str(error),
            "problems": problems,
        },
        status=status,
    )


ERROR_RESPONSES: dict[int, type[ErrorOut]] = {
    400: ErrorOut,
    401: ErrorOut,
    403: ErrorOut,
    404: ErrorOut,
    409: ErrorOut,
    422: ErrorOut,
    423: ErrorOut,
    500: ErrorOut,
    503: ErrorOut,
}


def api_response(success: Any) -> Any:
    """Объединяет успешные ответы операции с общими ошибками API."""
    responses = dict(success) if isinstance(success, dict) else {200: success}
    return {**ERROR_RESPONSES, **responses}


def _error_code(status: int) -> str:
    """Возвращает стабильный machine-readable код для HTTP-статуса."""
    return {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        409: "conflict",
        422: "validation_error",
        423: "resource_locked",
        503: "service_unavailable",
    }.get(status, "http_error")


def handle_http_error(request: HttpRequest, error: HttpError, *, api: Any) -> HttpResponse:
    """Возвращает единый JSON-ответ для явных HTTP-ошибок Ninja."""
    status = error.status_code
    return api.create_response(
        request,
        {
            "code": _error_code(status),
            "message": str(error),
            "problems": getattr(error, "problems", None),
        },
        status=status,
    )


def handle_authentication_error(
    request: HttpRequest, error: AuthenticationError, *, api: Any
) -> HttpResponse:
    """Formats Django Ninja's missing/invalid-auth response as the API contract."""
    return api.create_response(
        request,
        {
            "code": "unauthorized",
            "message": "A valid Bearer access token is required",
            "problems": None,
        },
        status=401,
    )


def handle_not_found(request: HttpRequest, error: Http404, *, api: Any) -> HttpResponse:
    """Преобразует Django Http404 в общий API-контракт ошибки."""
    return api.create_response(
        request,
        {"code": "not_found", "message": "Resource not found", "problems": None},
        status=404,
    )


def handle_validation_error(
    request: HttpRequest, error: ValidationError, *, api: Any
) -> HttpResponse:
    """Форматирует ошибки параметров и тел запросов единым списком problems."""
    problems = [
        {
            "location": list(problem.get("loc", ())),
            "message": problem.get("msg", "Invalid value"),
            "code": problem.get("type", "invalid"),
        }
        for problem in error.errors
    ]
    return api.create_response(
        request,
        {
            "code": "validation_error",
            "message": "Request validation failed",
            "problems": problems,
        },
        status=422,
    )


def handle_unexpected_error(
    request: HttpRequest, error: Exception, *, api: Any
) -> HttpResponse:
    """Логирует непредвиденную ошибку и не раскрывает внутренности клиенту."""
    logger.exception("Unhandled API exception", exc_info=error)
    return api.create_response(
        request,
        {
            "code": "internal_error",
            "message": "An unexpected error occurred",
            "problems": None,
        },
        status=500,
    )
