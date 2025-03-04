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
        is_html: bool = False,
        attachments: Optional[List[str]] = None
) -> bool:
    """
    Отправляет email с вложениями.

    Args:
        subject: Тема письма
        body: Текст письма
        is_html: Флаг HTML-формата
        attachments: Список путей к файлам-вложениям

    Returns:
        bool: Успешность отправки
    """
    try:
        msg = MIMEMultipart()
        msg["Subject"] = subject
        msg["From"] = EMAIL_USER
        msg["To"] = EMAIL_RECEIVER

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
            server.sendmail(EMAIL_USER, EMAIL_RECEIVER, msg.as_string())

        logger.info("Письмо успешно отправлено")
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