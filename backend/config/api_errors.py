import logging
from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404, HttpRequest, HttpResponse
from ninja import Schema
from ninja.errors import AuthenticationError, HttpError, ValidationError

from config.domain_errors import DomainError, error_code_for_status

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


def django_validation_problems(
    error: DjangoValidationError, location: tuple[str | int, ...] = ("body",)
) -> list[dict]:
    """Приводит результаты валидации модели Django к стандартному формату ошибок ErrorOut."""
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


def handle_domain_error(request: HttpRequest, error: DomainError, *, api: Any) -> HttpResponse:
    """Преобразует ожидаемую ошибку бизнес-операции в единый ErrorOut."""
    problems = error.problems
    if problems is None and error.validation_error is not None:
        problems = django_validation_problems(
            error.validation_error,
            error.validation_location,
        )
    return api.create_response(
        request,
        {
            "code": error.code,
            "message": str(error),
            "problems": problems,
        },
        status=error.status_code,
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


def handle_http_error(request: HttpRequest, error: HttpError, *, api: Any) -> HttpResponse:
    """Возвращает единый JSON-ответ для явных HTTP-ошибок Ninja."""
    status = error.status_code
    return api.create_response(
        request,
        {
            "code": error_code_for_status(status),
            "message": str(error),
            "problems": getattr(error, "problems", None),
        },
        status=status,
    )


def handle_authentication_error(
    request: HttpRequest, error: AuthenticationError, *, api: Any
) -> HttpResponse:
    """Форматирует ответ Django Ninja в случае отсутствия или недействительности аутентификационных данных в соответствии с API."""
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
    """Преобразует Django Http404 в общий API ошибки."""
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


def handle_unexpected_error(request: HttpRequest, error: Exception, *, api: Any) -> HttpResponse:
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
