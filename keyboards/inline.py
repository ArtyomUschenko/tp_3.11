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