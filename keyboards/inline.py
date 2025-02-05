from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Создание клавиатуры с кнопками "Назад" и "Отмена"
def get_back_cancel_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.insert(InlineKeyboardButton("❌ Отмена", callback_data="cancel"))
    keyboard.insert(InlineKeyboardButton("⬅️ Назад", callback_data="back"))
    return keyboard


def get_keyboard_start_menu() -> InlineKeyboardMarkup:
    ikb = InlineKeyboardMarkup(row_width=1)
    ib1 = InlineKeyboardButton('🆘 Оставить заявку', callback_data='start_support')
    ib2 = InlineKeyboardButton('💻 Официальный сайт', url="https://platform-eadsc.voskhod.ru/")
    ikb.add(ib1, ib2)
    return ikb


# @dp.message_handler(commands=['profile'], state="*")
# async def command_profile_process(message: types.Message, state: FSMContext):
#     result = await mysql.get_user_info(str(message.from_user.id))
#     text_profile = await get_profile.get_profile_data(result)
#     await message.answer(text_profile, reply_markup=inline.get_keyboard_menu_profile())
#
# @dp.callback_query_handler(Text(startswith='get_profile'), state="*")
# async def callback_get_profile(callback: types.CallbackQuery, state: FSMContext):
#     try:
#         await callback.answer(None)
#     except Exception as e:
#         logging.exception(f"Ошибка на ответ callback answer{e}")
#     result = await mysql.get_user_info(str(callback.from_user.id))
#     text_profile = await get_profile.get_profile_data(result)
#     await callback.message.answer(text_profile, disable_web_page_preview=True, reply_markup=inline.get_keyboard_menu_profile())

