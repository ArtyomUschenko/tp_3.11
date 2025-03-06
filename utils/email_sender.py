import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from date.config import EMAIL_HOST, EMAIL_PORT, EMAIL_USER, EMAIL_PASSWORD, EMAIL_RECEIVER
from email.mime.base import MIMEBase
from email import encoders
import logging
import os
from email.header import Header
from email.utils import encode_rfc2231
from typing import Optional, List

# Настройка логгера
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def send_email(
        subject: str,
        body: str,
        to_emails: List[str],
        is_html: bool = False,
        attachments: Optional[List[str]] = None
) -> bool:
    """
    Отправляет email с вложениями на несколько адресов.

    Args:
        subject: Тема письма
        body: Текст письма
        to_emails: Список адресов получателей
        is_html: Флаг HTML-формата
        attachments: Список путей к файлам-вложениям

    Returns:
        bool: Успешность отправки
    """
    try:
        # Проверка, что to_emails - это список
        if not isinstance(to_emails, list):
            raise ValueError("to_emails должен быть списком адресов электронной почты")

        # Проверка, что все элементы списка - строки
        if not all(isinstance(email, str) for email in to_emails):
            raise ValueError("Все элементы to_emails должны быть строками")

        msg = MIMEMultipart()
        msg["Subject"] = subject
        msg["From"] = EMAIL_USER
        msg["To"] = ", ".join(to_emails)  # Для заголовка письма

        msg.attach(MIMEText(body, "html" if is_html else "plain"))

        if attachments:
            for file_path in attachments:
                if not os.path.exists(file_path):
                    logger.error(f"Файл не найден: {file_path}")
                    continue
                attach_file(msg, file_path)

        with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            # Отправка на список адресов
            server.sendmail(EMAIL_USER, to_emails, msg.as_string())

        logger.info(f"Письмо успешно отправлено на {len(to_emails)} адресов")
        return True

    except Exception as e:
        logger.error(f"Ошибка отправки письма: {e}")
        return False


def attach_file(msg: MIMEMultipart, file_path: str) -> None:
    """Добавляет файл к письму."""
    try:
        with open(file_path, 'rb') as f:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(f.read())
            encoders.encode_base64(part)

        filename = os.path.basename(file_path)
        encoded_name = encode_rfc2231(filename, charset='utf-8')
        part.add_header('Content-Disposition', 'attachment', filename=encoded_name)

        msg.attach(part)
    except Exception as e:
        logger.error(f"Ошибка добавления вложения {file_path}: {e}")