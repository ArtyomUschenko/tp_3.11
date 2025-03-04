import re
import logging
from typing import Tuple

logger = logging.getLogger(__name__)


def is_valid_email(email: str) -> Tuple[bool, str]:
    """
    Проверяет корректность email адреса.

    Args:
        email: Проверяемый email адрес

    Returns:
        Tuple[bool, str]: (результат проверки, сообщение об ошибке)
    """
    # Проверка на пустое значение
    if not email or not email.strip():
        return False, "Email не может быть пустым"

    email = email.strip().lower()

    # Проверка длины
    if len(email) > 255:
        return False, "Email слишком длинный (максимум 255 символов)"

    # Проверка на наличие @
    if '@' not in email:
        return False, "Email должен содержать символ @"

    # Базовая проверка формата
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    if not re.match(pattern, email):
        return False, "Некорректный формат email"

    # Проверка количества символов @
    if email.count('@') != 1:
        return False, "Email должен содержать ровно один символ @"

    # Проверка локальной части и домена
    local_part, domain = email.split('@')

    # Проверка локальной части
    if not local_part:
        return False, "Отсутствует локальная часть email"
    if len(local_part) > 64:
        return False, "Локальная часть email слишком длинная (максимум 64 символа)"

    # Проверка домена
    if not domain:
        return False, "Отсутствует доменная часть email"
    if '.' not in domain:
        return False, "Некорректный домен (должен содержать минимум одну точку)"

    # Проверка частей домена
    domain_parts = domain.split('.')
    if not all(part and len(part) <= 63 for part in domain_parts):
        return False, "Некорректное доменное имя (части не должны быть пустыми и длиннее 63 символов)"
    if domain_parts[-1].isdigit():
        return False, "Последняя часть домена не может состоять только из цифр"

    logger.debug(f"Email {email} прошел валидацию")
    return True, ""