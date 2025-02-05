import logging
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.dispatcher import FSMContext
from aiogram.utils import executor
from date.config import TELEGRAM_TOKEN
from handlers import start, support
from utils.database import create_tables
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from handlers.callback_admin import handle_forwarded_message
from utils.thottling import ThrottlingMiddleware
from utils.notify_admins import on_startup_notify, on_shutdown_notify

# Настройка логгирования
logging.basicConfig(
    level=logging.INFO)

logger = logging.getLogger(__name__)
logger = logging.LoggerAdapter(logger, {"app": "тестовое приложение"})
logger.info("Программа стартует")
logger.info("Программа завершила работу")

# Иницилизация бота
bot =Bot(TELEGRAM_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())
dp.middleware.setup(LoggingMiddleware())


# Регистрация обработчиков
dp.register_message_handler(start.start, commands=["start"])
dp.register_message_handler(support.start_support, commands=["support"], state="*")
dp.register_message_handler(support.get_name, state=support.SupportStates.GET_NAME)
dp.register_message_handler(support.get_email, state=support.SupportStates.GET_EMAIL)
dp.register_message_handler(support.get_message, state=support.SupportStates.GET_MESSAGE)
dp.register_message_handler(handle_forwarded_message, is_forwarded=True)  # Новый обработчик
dp.register_callback_query_handler(support.cancel_handler, lambda c: c.data == "cancel", state="*")
dp.register_callback_query_handler(support.back_handler, lambda c: c.data == "back", state="*")

from handlers.support import register_admin_handlers
register_admin_handlers(dp)

from handlers.callback_admin import register_admin
register_admin(dp)


# Уведомление об остановки бота
async def on_shutdown(app):
    await on_shutdown_notify(dp)

# Инициализация базы данных при запуске
async def on_startup(dp):
    await on_startup_notify(dp)
    await create_tables()

# Запуск бота
if __name__ == "__main__":
    dp.middleware.setup(ThrottlingMiddleware())
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup, on_shutdown=on_shutdown)