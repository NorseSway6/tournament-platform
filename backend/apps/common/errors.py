from django.core.exceptions import ValidationError

STATUS_CODES: dict[int, str] = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    409: "conflict",
    422: "validation_error",
    423: "resource_locked",
    500: "internal_error",
    503: "service_unavailable",
}


def error_code_for_status(status_code: int) -> str:
    """Возвращает стабильный machine-readable код для HTTP-статуса."""
    return STATUS_CODES.get(status_code, "http_error")


class DomainError(Exception):
    """Базовый класс ожидаемого отказа бизнес-операции."""

    status_code = 409
    code = "conflict"

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        *,
        code: str | None = None,
        problems: list[dict] | None = None,
        validation_error: ValidationError | None = None,
        validation_location: tuple[str | int, ...] = ("body",),
    ) -> None:
        super().__init__(message)
        if status_code is not None:
            self.status_code = status_code
            self.code = error_code_for_status(status_code)
        if code is not None:
            self.code = code
        self.problems = problems
        self.validation_error = validation_error
        self.validation_location = validation_location


class BadRequestError(DomainError):
    """Некорректный запрос, который не прошёл проверку бизнес-правил."""

    status_code = 400
    code = "bad_request"


class UnauthorizedError(DomainError):
    """Запрос не содержит действительных учётных данных."""

    status_code = 401
    code = "unauthorized"


class ForbiddenError(DomainError):
    """У пользователя нет прав на выполнение операции."""

    status_code = 403
    code = "forbidden"


class NotFoundError(DomainError):
    """Запрошенный ресурс не существует или недоступен."""

    status_code = 404
    code = "not_found"


class ConflictError(DomainError):
    """Операция конфликтует с текущим состоянием ресурса."""

    status_code = 409
    code = "conflict"


class DomainValidationError(DomainError):
    """Данные не прошли предметную валидацию."""

    status_code = 422
    code = "validation_error"


class ResourceLockedError(DomainError):
    """Ресурс временно заблокирован другой операцией."""

    status_code = 423
    code = "resource_locked"


class ServiceUnavailableError(DomainError):
    """Зависимость, необходимая для операции, временно недоступна."""

    status_code = 503
    code = "service_unavailable"
