import re
from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils.email_sender import send_email
from utils.database import create_connection
from date.config  import ADMIN_ID, ADMIN_IDS
import logging

# Настройка логгера
logging.basicConfig(level=logging.INFO)

# Состояния для администратора
class AdminStates(StatesGroup):
    WAITING_FOR_REPLY = State()

# Состояния для FSM
class SupportStates(StatesGroup):
    GET_NAME = State()
    GET_EMAIL = State()
    GET_MESSAGE = State()

# Валидация email
def is_valid_email(email: str) -> bool:
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return re.match(pattern, email) is not None

# Создание клавиатуры с кнопками "Назад" и "Отмена"
def get_back_cancel_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.insert(InlineKeyboardButton("❌ Отмена", callback_data="cancel"))
    keyboard.insert(InlineKeyboardButton("↩️ Назад", callback_data="back"))
    return keyboard

async def handle_forwarded_message(message: types.Message, state: FSMContext):
    # Проверяем, что сообщение отправлено администратором
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("Эта функция доступна только сотрудникам ТП.")
        return

    # Проверяем, что сообщение переслано
    if not message.forward_from:
        await message.answer("Это сообщение не является пересланным.")
        return

    # Парсим информацию из пересланного сообщения
    user_id = message.forward_from.id
    user_username = message.forward_from.username
    user_name = message.forward_from.full_name
    forwarded_text = message.text or message.caption  # Текст или подпись к медиа
    admin_id = message.from_user.id
    admin_name = message.from_user.full_name  # Имя администратора

    # Проверяем, есть ли текст в сообщении
    if not forwarded_text:
        await message.answer("Пересланное сообщение не содержит текста.")
        return

    #Сохраняем заявку в базу данных
    conn = await create_connection()
    await conn.execute(
        "INSERT INTO support_requests (user_id, user_username, name, message, admin_id, admin_name) VALUES ($1, $2, $3, $4, $5, $6)",
        user_id, user_username, user_name, forwarded_text, admin_id, admin_name
    )
    await conn.close()

    # Уведомление администратору
    admin_text = (
        "🚨 Новая заявка в поддержку!\n"
        f"👤 Пользователь: {user_id}\n"
        f"📛 Имя: {user_name}\n"
        f"📝 Сообщение:\n{forwarded_text}"
    )

    try:
        await message.bot.send_message(
            chat_id=ADMIN_ID,
            text=admin_text
        )
    except Exception as e:
        logging.error(f"Ошибка отправки уведомления админу: {e}")

    await message.answer("Заявка успешно создана на основе пересланного сообщения.")


    # Формируем текст письма
    email_text = (
        f"Сотрудник ТП завел заявку через чат.<br><br>"
        f"Имя: <b>{user_name}</b><br>"
        f"ID пользователя: <b>{user_id}</b><br>"
        f"Ссылка в tg: <b>https://t.me/{user_username}</b><br>"
        # f"Email: <b>{email}</b><br>"
        f"Текст обращения: <b>{forwarded_text}</b><br><br>"

        f"<i>Сообщение переслал сотрудник ТП:</i><br>"
        f"ID: {admin_id}<br>"
        f"Имя: {admin_name}"
    )

    # Отправляем письмо
    send_email("Вопрос от пользователя через чат ГИС “Платформа “ЦХЭД”", body=email_text,
               is_html=True)

    await message.answer("Ваша заявка отправлена. Спасибо!")


# Обработчик кнопки "Отмена"
async def cancel_handler(callback: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await callback.message.edit_text("Операция отменена.")
    await callback.message.answer(
        "Используйте команду /support, чтобы отправить заявку в техническую поддержку.",
        reply_markup=None  # Убираем клавиатуру
    )
    await callback.answer()

# Начало заполнения заявки
async def start_support(message: types.Message, state: FSMContext):
    cancel_keyboard = InlineKeyboardMarkup(row_width=1)
    cancel_keyboard.add(InlineKeyboardButton("❌ Отмена", callback_data="cancel"))
    await message.answer("Пожалуйста, введите ваше имя:", reply_markup=cancel_keyboard)
    await state.set_state(SupportStates.GET_NAME.state)

async def get_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    keyboard = get_back_cancel_keyboard()
    await message.answer("Введите ваш email:", reply_markup=keyboard)
    await state.set_state(SupportStates.GET_EMAIL.state)

async def get_email(message: types.Message, state: FSMContext):
    if not is_valid_email(message.text):
        await message.answer("Некорректный email. Пожалуйста, введите email еще раз.")
        return

    await state.update_data(email=message.text)
    keyboard = get_back_cancel_keyboard()
    await message.answer("Опишите вашу проблему:", reply_markup=keyboard)
    await state.set_state(SupportStates.GET_MESSAGE.state)


    username = message.from_user.username

async def get_message(message: types.Message, state: FSMContext):
    # Извлекаем username пользователя
    username = message.from_user.username

    user_data = await state.get_data()
    username = username
    name = user_data.get("name")
    email = user_data.get("email")
    problem = message.text
    user_id = message.from_user.id

    # Сохраняем заявку в базу данных
    conn = await create_connection()
    await conn.execute(
        "INSERT INTO support_requests (user_id, name, user_username, email, message) VALUES ($1, $2, $3, $4, $5)",
        message.from_user.id,  name, username, email, problem
    )
    await conn.close()

    # Уведомление администратору
    admin_text = (
        "🚨 Новая заявка в поддержку!\n"
        f"👤 Пользователь: {user_id}\n"
        f"👤 Ссылка в tg: @{username if username else 'Не указан'}\n"
        f"📛 Имя: {name}\n"
        f"📧 Email: {email}\n"
        f"📝 Сообщение:\n{problem}"
    )

    # Создаем инлайн-кнопки
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton(
            "✉️ Ответить",
            callback_data=f"reply_{user_id}"
        )
    )

    try:
        await message.bot.send_message(
            chat_id=ADMIN_ID,
            text=admin_text,
            reply_markup=keyboard
        )
    except Exception as e:
        logging.error(f"Ошибка отправки уведомления админу: {e}")


    # Формируем текст письма
    email_text = (
        f"Пользователь оставил запрос в техническую поддержку через чат.<br><br>"
        f"Имя: <b>{name}</b><br>"
        f"Email: <b>{email}</b><br>"
        f"Ссылка в tg: <b>https://t.me/{username if username else 'Не_указан'}</b><br>"
        f"Текст обращения: <b>{problem}</b>"
    )

    # Отправляем письмо
    send_email("Вопрос от пользователя через чат ГИС “Платформа “ЦХЭД”", body=email_text,
    is_html=True)

    await message.answer("Ваша заявка отправлена. Спасибо!")
    await state.finish()

# Обработчик кнопки "Назад"
async def back_handler(callback: types.CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    if current_state == SupportStates.GET_EMAIL.state:
        keyboard = get_back_cancel_keyboard()
        await state.set_state(SupportStates.GET_NAME.state)
        await callback.message.edit_text("Пожалуйста, введите ваше имя:", reply_markup=keyboard)
    elif current_state == SupportStates.GET_MESSAGE.state:
        keyboard = get_back_cancel_keyboard()
        await state.set_state(SupportStates.GET_EMAIL.state)
        await callback.message.edit_text("Введите ваш email:", reply_markup=keyboard)
    await callback.answer()

# Обработчики кнопок
async def handle_admin_callback(callback: types.CallbackQuery, state: FSMContext):
    action, data = callback.data.split("_")

    if action == "reply":
        await state.update_data(target_user_id=data)
        await callback.message.answer("Введите ваш ответ:")
        await AdminStates.WAITING_FOR_REPLY.set()

    elif action == "view":
        # Здесь можно добавить логику просмотра заявки из БД
        await callback.answer("Заявка будет показана здесь", show_alert=True)

    await callback.answer()

async def handle_admin_reply(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    target_user_id = user_data.get("target_user_id")

    try:
        await message.bot.send_message(
            chat_id=target_user_id,
            text=f"📨 Ответ от поддержки:\n\n{message.text}"
        )
        await message.answer("✅ Ответ успешно отправлен!")
    except Exception as e:
        await message.answer("❌ Ошибка отправки ответа")
        logging.error(f"Ошибка отправки ответа: {e}")

    await state.finish()

# Регистрация обработчиков
def register_admin_handlers(dp: Dispatcher):
    dp.register_callback_query_handler(
        handle_admin_callback,
        lambda c: c.data.startswith(("reply_", "view_"))
    )
    dp.register_message_handler(
        handle_admin_reply,
        state=AdminStates.WAITING_FOR_REPLY
    )
