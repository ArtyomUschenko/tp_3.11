import os
from dotenv import load_dotenv
from typing import List

# Загружаем переменные окружения
load_dotenv()

# Токен бота
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# Данные для отправки email
EMAIL_HOST = os.getenv("EMAIL_HOST")
EMAIL_PORT = os.getenv("EMAIL_PORT")
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
# EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")

# Данные для подключения к PostgreSQL
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_USER = os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
POSTGRES_DB = os.getenv("POSTGRES_DB")

# Админы
ADMIN_ID = os.getenv("ADMIN_ID")

ADMIN_IDS = [int(id) for id in os.getenv("ADMIN_IDS").split(",")]
EMAIL_RECEIVER = [str(id) for id in os.getenv("EMAIL_RECEIVER").split(",")]