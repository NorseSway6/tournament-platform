from django.core.exceptions import ValidationError


class DomainError(Exception):
    """Представляет ожидаемый отказ бизнес-операции.

    Сервис указывает сообщение и код результата, а общий API-обработчик
    преобразует ошибку в публичный ErrorOut. Сервисам не нужно знать о Ninja.
    """

    def __init__(
        self,
        message: str,
        status_code: int = 409,
        *,
        problems: list[dict] | None = None,
        validation_error: ValidationError | None = None,
        validation_location: tuple[str | int, ...] = ("body",),
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.problems = problems
        self.validation_error = validation_error
        self.validation_location = validation_location
