from aiogram import types

#Список команд при нажатии на кнопку Меню
async def set_default_commands(dp):
    await dp.bot.set_my_commands(
        [
            types.BotCommand("start", "оставить заявку")
        ]
    )