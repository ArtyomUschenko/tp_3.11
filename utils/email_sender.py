import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from date.config  import EMAIL_HOST, EMAIL_PORT, EMAIL_USER, EMAIL_PASSWORD, EMAIL_RECEIVER

def send_email(subject: str, body: str, is_html: bool= False):
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



    # Отправляем письмо
    with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as server:
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_USER, EMAIL_RECEIVER, msg.as_string())