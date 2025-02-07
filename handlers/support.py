from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils.email_sender import send_email
from utils.valid_email import is_valid_email
from utils.database import create_connection
from date.config  import ADMIN_ID, ADMIN_IDS
from states import user_state, admin_state
from keyboards import inline
import logging

# Настройка логгера
logging.basicConfig(level=logging.INFO)

# Начало заполнения заявки
async def start_support(message: types.Message, state: FSMContext):
    consent_keyboard = InlineKeyboardMarkup(row_width=2)
    consent_keyboard.add(
        InlineKeyboardButton("✅ Согласен", callback_data="consent_yes"),
        InlineKeyboardButton("❌ Отмена", callback_data="cancel")
    )

    # Текст согласия (используется HTML-форматирование)
    text = (
        "Вы даете согласие на обработку персональных данных?\n\n"
        "[Политика в отношении обработки и защиты персональных данных](https://platform-eadsc.voskhod.ru/docs_back/personal_data_processing_policy.pdf)"
    )
    # Отправляем сообщение с HTML-форматированием
    await message.answer(text, reply_markup=consent_keyboard, parse_mode=types.ParseMode.MARKDOWN)
    await state.set_state(user_state.SupportStates.GET_CONSENT.state)  # Устанавливаем новое состояние


async def handle_consent(callback: types.CallbackQuery, state: FSMContext):
    if callback.data == "consent_yes":
        cancel_keyboard = InlineKeyboardMarkup(row_width=1)
        cancel_keyboard.add(InlineKeyboardButton("❌ Отмена", callback_data="cancel"))

        await callback.message.edit_text("Пожалуйста, введите ваше имя:", reply_markup=cancel_keyboard)
        await state.set_state(user_state.SupportStates.GET_NAME.state)

    elif callback.data == "cancel":
        await state.finish()
        await callback.message.edit_text("Операция отменена.")

    await callback.answer()

async def get_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    keyboard = inline.get_back_cancel_keyboard()
    await message.answer("Введите ваш email:", reply_markup=keyboard)
    await state.set_state(user_state.SupportStates.GET_EMAIL.state)

async def get_email(message: types.Message, state: FSMContext):
    if not is_valid_email(message.text):
        await message.answer("Некорректный email. Пожалуйста, введите email еще раз.")
        return

    await state.update_data(email=message.text)
    keyboard = inline.get_back_cancel_keyboard()
    await message.answer("Опишите вашу проблему:", reply_markup=keyboard)
    await state.set_state(user_state.SupportStates.GET_MESSAGE.state)


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


# ///////////Кнопки\\\\\\\\\

# Обработчик кнопки "Назад"
async def back_handler(callback: types.CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    if current_state == user_state.SupportStates.GET_EMAIL.state:
        keyboard = inline.get_back_cancel_keyboard()
        await state.set_state(user_state.SupportStates.GET_NAME.state)
        await callback.message.edit_text("Пожалуйста, введите ваше имя:", reply_markup=keyboard)
    elif current_state == user_state.SupportStates.GET_MESSAGE.state:
        keyboard = inline.get_back_cancel_keyboard()
        await state.set_state(user_state.SupportStates.GET_EMAIL.state)
        await callback.message.edit_text("Введите ваш email:", reply_markup=keyboard)
    await callback.answer()







# Обработчик кнопки "Оставить заявку"
async def start_support_handler(callback: types.CallbackQuery, state: FSMContext):
    try:
        await callback.answer()  # Ответ на callback без дополнительных данных
    except Exception as e:
        logging.exception(f"Ошибка на ответ callback answer: {e}")

    # Создаем клавиатуру с кнопкой "Отмена"
    consent_keyboard = InlineKeyboardMarkup(row_width=2)
    consent_keyboard.add(
        InlineKeyboardButton("✅ Согласен", callback_data="consent_yes"),
        InlineKeyboardButton("❌ Отмена", callback_data="cancel")
    )

    # Текст согласия (используется HTML-форматирование)
    text = (
        "Вы даете согласие на обработку персональных данных?\n\n"
        "[Политика в отношении обработки и защиты персональных данных](https://platform-eadsc.voskhod.ru/docs_back/personal_data_processing_policy.pdf)"
    )


    # Уведомляем пользователя о начале заполнения заявки
    await callback.message.answer(text, reply_markup=consent_keyboard, parse_mode=types.ParseMode.MARKDOWN)

    # Устанавливаем состояние GET_NAME для начала сбора данных
    await state.set_state(user_state.SupportStates.GET_CONSENT.state)


# Обработчик кнопки "Отмена"
async def cancel_handler(callback: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await callback.message.edit_text("Операция отменена.")
    await callback.message.answer(
        "Используйте команду /support, чтобы отправить заявку в техническую поддержку.",
        reply_markup=None  # Убираем клавиатуру
    )
    await callback.answer()

# Обработчик кнопки "Пропустить"
async def skip_email(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(email=None)
    await callback.message.delete()  # Удаляем сообщение с клавиатурой
    await process_forwarded_request(callback.message, state)  # Продолжаем обработку

async def process_forwarded_request(message: types.Message, state: FSMContext):
    data = await state.get_data()

    # Сохраняем заявку без email
    conn = await create_connection()
    await conn.execute(
        """INSERT INTO support_requests 
        (user_id, user_username, name, message, admin_id, admin_name) 
        VALUES ($1, $2, $3, $4, $5, $6)""",
        data['user_id'],
        data['user_username'],
        data['user_name'],
        data['forwarded_text'],
        data['admin_id'],
        data['admin_name']
    )
    await conn.close()

    # Уведомление администратору
    admin_text = (
        "🚨 Новая заявка в поддержку!\n"
        f"👤 Пользователь: {data['user_id']}\n"
        f"📛 Имя: {data['user_name']}\n"
        f"📝 Сообщение:\n{data['forwarded_text']}"
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
        f"Имя: <b>{data['user_name']}</b><br>"
        f"Email: <b>{data.get('email', 'не указан')}</b><br>"
        f"ID пользователя: <b>{data['user_id']}</b><br>"
        f"Ссылка в tg: <b>https://t.me/{data['user_username']}</b><br>"
        f"Текст обращения: <b>{data['forwarded_text']}</b><br><br>"

        f"<i>Сообщение переслал сотрудник ТП:</i><br>"
        f"ID: {data['admin_id']}<br>"
        f"Имя: {data['admin_name']}"
    )

    # Отправляем письмо
    send_email("Вопрос от пользователя через чат ГИС “Платформа “ЦХЭД”", body=email_text,
               is_html=True)

    await message.answer("Ваша заявка отправлена. Спасибо!")
    await state.finish()



# Обработчики кнопок
async def handle_admin_callback(callback: types.CallbackQuery, state: FSMContext):
    action, data = callback.data.split("_")

    if action == "reply":
        await state.update_data(target_user_id=data)
        await callback.message.answer("Введите ваш ответ:")
        await admin_state.AdminStates.WAITING_FOR_REPLY.set()

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




