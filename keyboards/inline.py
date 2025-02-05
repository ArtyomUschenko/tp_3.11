from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Создание клавиатуры с кнопками "Назад" и "Отмена"
def get_back_cancel_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.insert(InlineKeyboardButton("❌ Отмена", callback_data="cancel"))
    keyboard.insert(InlineKeyboardButton("⬅️ Назад", callback_data="back"))
    return keyboard
