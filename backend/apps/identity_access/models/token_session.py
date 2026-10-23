import uuid

from django.conf import settings
from django.db import models


class TokenSession(models.Model):
    """Сессия двухтокенной авторизации с хешем ротируемого refresh-токена."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="token_sessions",
    )
    refresh_token_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["user", "revoked_at"], name="identity_token_user_idx")]

    def __str__(self) -> str:
        """Показывает владельца и срок сессии без раскрытия токенов."""
        return f"Token session for user {self.user_id} (expires {self.expires_at})"
