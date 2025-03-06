import logging
from aiogram import Dispatcher
from date.config import ADMIN_IDS

#Уведомления админа при запуске или остановке бота
async def on_startup_notify(dp: Dispatcher):
    for admin in ADMIN_IDS:
        try:
            await dp.bot.send_message(admin, "Бот запущен")
        except Exception as err:
            logging.exception(err)

async def on_shutdown_notify(dp: Dispatcher):
    for admin in ADMIN_IDS:
        try:
            await dp.bot.send_message(admin, "Бот остановлен")
        except Exception as err:
            logging.exception(err)