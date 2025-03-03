import logging
from aiogram import Bot, Dispatcher
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.utils import executor
from date.config import TELEGRAM_TOKEN
from handlers import start, support, callback_admin
from utils.database import create_tables
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from middlewares.thottling import ThrottlingMiddleware
from utils.notify_admins import on_startup_notify, on_shutdown_notify
from states import user_state, admin_state
from utils.set_bot_commands import set_default_commands
from aiogram import types


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
dp.register_message_handler(support.get_name, state=user_state.SupportStates.GET_NAME)
dp.register_message_handler(support.get_email, state=user_state.SupportStates.GET_EMAIL)
dp.register_message_handler(support.get_message, state=user_state.SupportStates.GET_MESSAGE)
dp.register_message_handler(callback_admin.handle_forwarded_message, is_forwarded=True, content_types=types.ContentType.ANY, state="*")  # Новый обработчик
dp.register_callback_query_handler(support.cancel_handler, lambda c: c.data == "cancel", state="*")
dp.register_callback_query_handler(support.back_handler, lambda c: c.data == "back", state="*")
dp.register_message_handler(support.handle_admin_reply, state=admin_state.AdminStates.WAITING_FOR_REPLY)
dp.register_callback_query_handler(callback_admin.skip_email,lambda c: c.data == "skip_email",state=user_state.SupportStates.GET_EMAIL_FORWARDED)
dp.register_callback_query_handler(callback_admin.cancel_handler, lambda c: c.data == "cancel", state="*")
dp.register_message_handler(callback_admin.get_forwarded_email,state=user_state.SupportStates.GET_EMAIL_FORWARDED)
dp.register_callback_query_handler(support.start_support, lambda c: c.data == "start_support")
dp.register_callback_query_handler(support.handle_admin_callback, lambda c: c.data.startswith("reply_") or c.data.startswith("view_"))
dp.register_callback_query_handler(support.handle_consent, lambda c: c.data in ["consent_yes", "cancel"], state=user_state.SupportStates.GET_CONSENT)
dp.register_callback_query_handler(support.handle_file_choice, state=user_state.SupportStates.GET_FILE)
dp.register_message_handler(support.upload_file, state=user_state.SupportStates.GET_FILE_UPLOAD, content_types=['document', 'photo'])
dp.register_callback_query_handler(support.handle_file_choice, lambda c: c.data in ["yes_support", "no_support"], state=user_state.SupportStates.GET_FILE)


# Уведомление об остановки бота
async def on_shutdown(app):
    await on_shutdown_notify(dp)

# Инициализация базы данных при запуске
async def on_startup(dp):
    await set_default_commands(dp)
    await on_startup_notify(dp)
    await create_tables()


# Запуск бота
if __name__ == "__main__":
    dp.middleware.setup(ThrottlingMiddleware())
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup, on_shutdown=on_shutdown)