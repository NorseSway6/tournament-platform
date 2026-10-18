from .user import User


class AdminUser(User):
    """Прокси-модель для представления пользователей в отдельном разделе админки"""

    class Meta:
        proxy = True
