from aiogram import types
from aiogram.types import InputFile
from middlewares.rate_limit import rate_limit
from keyboards import inline

#
# async def start(massage: types.Message):
#     photo = InputFile("./img/tshed_logo.png")
#     await massage.answer("Привет! Я бот технической поддержки. Используйте команду /support")
#

@rate_limit(limit=10, key='/start')
async def start(message: types.Message):
    photo = "./img/tshed_logo.jpg"

    # Текст сообщения
    welcome_text = (
        "\n\n👋 Привет! Я бот технической поддержки ЦХЭД.\n\n"
    )

    # Отправляем изображение и текст
    with open(photo, "rb") as photo:
        await message.answer_photo(
            photo=InputFile(photo),
            caption=welcome_text, reply_markup=inline.get_keyboard_start_menu()
        )