from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q

phone_validator = RegexValidator(
    regex=r"^\+[1-9]\d{1,14}$",
    message="Enter a phone number in E.164 format, for example +15551234567.",
)


class User(AbstractUser):
    email = models.EmailField(unique=True, null=True, blank=True)
    phone = models.CharField(
        max_length=16, unique=True, null=True, blank=True, validators=[phone_validator]
    )
    telegram_id = models.BigIntegerField(unique=True, null=True, blank=True)
    telegram_username = models.CharField(max_length=64, blank=True)
    display_name = models.CharField(max_length=150, blank=True)
    is_platform_admin = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(phone__isnull=False)
                    | (Q(email__isnull=False) & ~Q(email=""))
                    | Q(telegram_id__isnull=False)
                ),
                name="identity_user_has_identifier",
            ),
        ]

    def __str__(self) -> str:
        return (
            self.display_name
            or self.get_full_name()
            or self.phone
            or self.email
            or self.username
        )
