import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from date.config  import EMAIL_HOST, EMAIL_PORT, EMAIL_USER, EMAIL_PASSWORD, EMAIL_RECEIVER
from email.mime.base import MIMEBase
from email import encoders
import logging
import os

# Настройка логгера
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)



# Формирования и отправка письма на почту
def send_email(subject: str, body: str, is_html: bool= False, attachments: list = None):
    # Создаем сообщение
    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = EMAIL_USER
    msg["To"] = EMAIL_RECEIVER

    # Добавляем тело письма
    if is_html:
        msg.attach(MIMEText(body, "html"))
    else:
        msg.attach(MIMEText(body, "plain"))

    # Прикрепляем файлы, если они есть
    if attachments:
        for file_path in attachments:
            if file_path and os.path.exists(file_path):
                with open(file_path, 'rb') as f:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header(
                        'Content-Disposition',
                        f'attachment; filename={os.path.basename(file_path)}'
                    )
                    msg.attach(part)

    # Отправляем письмо
    try:
        with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_USER, EMAIL_RECEIVER, msg.as_string())
    except Exception as e:
        logger.error(f"Ошибка отправки письма: {e}")