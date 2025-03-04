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

# Настройка логгера
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def send_email(subject: str, body: str, is_html: bool = False, attachments: list = None):
    # Создаем сообщение
    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = EMAIL_USER
    msg["To"] = EMAIL_RECEIVER

    # Добавляем тело письма
    msg.attach(MIMEText(body, "html" if is_html else "plain"))

    # Прикрепляем файлы, если они есть
    if attachments:
        for file_path in attachments:
            if file_path and os.path.exists(file_path):
                # Извлекаем имя файла из пути
                file_name = os.path.basename(file_path)
                logger.info(f"Attaching file: {file_name} from path: {file_path}")
                with open(file_path, 'rb') as f:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(f.read())
                    encoders.encode_base64(part)
                    # Используем RFC 2231 для корректной обработки не-ASCII имен
                    encoded_file_name = encode_rfc2231(file_name, charset='utf-8')
                    part.add_header(
                        'Content-Disposition',
                        'attachment',
                        filename=encoded_file_name
                    )
                    msg.attach(part)
            else:
                logger.error(f"File not found for attachment: {file_path}")

    # Отправляем письмо
    try:
        with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_USER, EMAIL_RECEIVER, msg.as_string())
            logger.info("Письмо успешно отправлено")
    except Exception as e:
        logger.error(f"Ошибка отправки письма: {e}")