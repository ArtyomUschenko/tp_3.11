import re
from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from utils.email_sender import send_email
from utils.database import create_connection
from date.config  import ADMIN_ID, ADMIN_IDS
import logging

# Состояния для FSM
class SupportStates(StatesGroup):
    GET_NAME = State()
    GET_EMAIL = State()
    GET_MESSAGE = State()

async def handle_forwarded_message(message: types.Message, state: FSMContext):
    # Проверяем, что сообщение отправлено администратором
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("Эта функция доступна только администраторам.")
        return


    # Проверяем, что сообщение переслано
    if not message.forward_from:
        await message.answer("Это сообщение не является пересланным.")
        return

    # Парсим информацию из пересланного сообщения
    user_id = message.forward_from.id
    user_name = message.forward_from.full_name
    forwarded_text = message.text or message.caption  # Текст или подпись к медиа
    admin_id = message.from_user.id
    admin_name = message.from_user.full_name  # Имя администратора

    # # Сохраняем данные администратора в FSM
    # await state.update_data(admin_id=admin_id, admin_name=admin_name)

    # Проверяем, есть ли текст в сообщении
    if not forwarded_text:
        await message.answer("Пересланное сообщение не содержит текста.")
        return

    # Сохраняем заявку в базу данных
    conn = await create_connection()
    await conn.execute(
        "INSERT INTO support_requests (user_id, name, message, admin_id, admin_name) VALUES ($1, $2, $3, $4, $5)",
        user_id, user_name, forwarded_text, admin_id, admin_name
    )
    await conn.close()

    # # Формируем текст письма
    # email_text = (
    #     f"Новая заявка от {user_name} (ID: {user_id}):\n\n"
    #     f"{forwarded_text}"
    # )
    #
    # # Отправляем письмо
    # send_email("Новая заявка в поддержку", email_text)

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



# Валидация email
def is_valid_email(email: str) -> bool:
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return re.match(pattern, email) is not None

async def start_support(message: types.Message, state: FSMContext):
    await message.answer("Пожалуйста, введите ваше имя:")
    await state.set_state(SupportStates.GET_NAME.state)

async def get_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Введите ваш email:")
    await state.set_state(SupportStates.GET_EMAIL.state)

async def get_email(message: types.Message, state: FSMContext):
    if not is_valid_email(message.text):
        await message.answer("Некорректный email. Пожалуйста, введите email еще раз.")
        return

    await state.update_data(email=message.text)
    await message.answer("Опишите вашу проблему:")
    await state.set_state(SupportStates.GET_MESSAGE.state)

async def get_message(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    name = user_data.get("name")
    email = user_data.get("email")
    problem = message.text
    user_id = message.from_user.id

    # Сохраняем заявку в базу данных
    conn = await create_connection()
    await conn.execute(
        "INSERT INTO support_requests (user_id, name, email, message) VALUES ($1, $2, $3, $4)",
        message.from_user.id, name, email, problem
    )
    await conn.close()

    # Уведомление администратору
    admin_text = (
        "🚨 Новая заявка в поддержку!\n"
        f"👤 Пользователь: {user_id}\n"
        f"📛 Имя: {name}\n"
        f"📧 Email: {email}\n"
        f"📝 Сообщение:\n{problem}"
    )

    try:
        await message.bot.send_message(
            chat_id=ADMIN_ID,
            text=admin_text
        )
    except Exception as e:
        logging.error(f"Ошибка отправки уведомления админу: {e}")


    # Формируем текст письма
    email_text = (
        f"Пользователь оставил запрос в техническую поддержку через чат.<br><br>"
        f"Имя: <b>{name}</b><br>"
        f"Email: <b>{email}</b><br>"
        f"Текст обращения: <b>{problem}</b>"
    )

    # Отправляем письмо
    send_email("Вопрос от пользователя через чат ГИС “Платформа “ЦХЭД”", body=email_text,
    is_html=True)

    await message.answer("Ваша заявка отправлена. Спасибо!")
    await state.finish()