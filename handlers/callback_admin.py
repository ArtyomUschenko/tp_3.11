from aiogram import types, Dispatcher
from date.config  import ADMIN_ID, ADMIN_IDS
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils.email_sender import send_email
from utils.database import create_connection
from utils.valid_email import is_valid_email
from states import user_state
import logging
import os
from aiogram import Bot
from aiogram.utils.exceptions import TelegramAPIError

# Настройка логгера
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)





# Путь для временного хранения файлов
from date.config import TELEGRAM_TOKEN
TEMP_DIR = "temp_files"
os.makedirs(TEMP_DIR, exist_ok=True)
bot =Bot(TELEGRAM_TOKEN)
# Функция для скачивания файла
async def download_file(file_id: str, file_type: str) -> str:
    file_path = f"{TEMP_DIR}/{file_id}_{file_type}"
    file = await bot.get_file(file_id)
    await file.download(destination_file=file_path)
    logger.info(f"File downloaded: {file_path}")
    return file_path






# Обработчик пересланных сообщений
async def handle_forwarded_message(message: types.Message, state: FSMContext):
    logger.info(f"Handling forwarded message: {message}")
    # Проверяем права администратора
    if message.from_user.id not in ADMIN_IDS:
        logger.warning(f"User {message.from_user.id} is not an admin")
        await message.answer("Эта функция доступна только сотрудникам ТП.")
        return

        # Проверяем, что сообщение переслано
    if not message.forward_from and not hasattr(message, "forward_sender_name"):
        logger.warning("Message is not properly forwarded")
        await message.answer("Это сообщение не является корректно пересланным.")
        return

    logger.info("Message is properly forwarded")

    # Извлекаем основные данные пользователя из пересланного сообщения
    user_data = {
        "user_id": message.forward_from.id if message.forward_from else None,
        "user_username": message.forward_from.username if message.forward_from else None,
        "user_name": (
            message.forward_from.full_name if message.forward_from else message.forward_sender_name
        ),
        "forwarded_text": message.text or message.caption,
        "admin_id": message.from_user.id,
        "admin_name": message.from_user.full_name,
        "document_id": None,
        "photo_id": None
    }

    # Проверяем, содержит ли сообщение документ
    if message.document:
        file_path = await download_file(message.document.file_id, "document")
        user_data["document_path"] = file_path
        logger.info(f"Document detected: {file_path}")
    elif message.photo:
        file_path = await download_file(message.photo[-1].file_id, "photo")
        user_data["photo_path"] = file_path
        logger.info(f"Photo detected: {file_path}")
    elif message.text:
        logger.info(f"Text message detected: {message.text}")
    else:
        logger.warning("Unsupported message type")
        await message.answer("Неподдерживаемый тип сообщения.")
        return

    # Сохраняем данные в FSM
    await state.update_data(**user_data)

    # Создаем клавиатуру с кнопкой "Пропустить"
    keyboard = InlineKeyboardMarkup()
    keyboard.row(
        InlineKeyboardButton("❌ Отмена", callback_data="cancel"),
        InlineKeyboardButton("⏭ Пропустить", callback_data="skip_email")
    )

    # Запрашиваем email пользователя
    await message.answer(
        "Введите email пользователя (или нажмите 'Пропустить'):",
        reply_markup=keyboard
    )
    await state.set_state(user_state.SupportStates.GET_EMAIL_FORWARDED.state)


# Добавим новый обработчик для email
async def get_forwarded_email(message: types.Message, state: FSMContext):
    email = message.text.strip()
    # Если email не пустой и невалидный
    if email and not is_valid_email(email):
        await message.answer("❌ Некорректный email. Попробуйте еще раз:")
        return

    # Сохраняем email (может быть None)
    await state.update_data(email=email if email else None)

    # Продолжаем обработку
    data = await state.get_data()

    logger.info(f"Saving support request: {data}")

    # Сохраняем заявку в БД
    try:
        conn = await create_connection()
        await conn.execute(
            """INSERT INTO support_requests 
            (user_id, user_username, name, email, message, admin_id, admin_name, document_id, photo_id) 
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)""",
            data['user_id'],
            data['user_username'],
            data['user_name'],
            data.get('email'),  # Email может быть None
            data['forwarded_text'],
            data['admin_id'],
            data['admin_name'],
            data.get('document_path'),  # Путь к документу
            data.get('photo_path')  # Путь к фото
        )
        await conn.close()
    except Exception as e:
        logger.error(f"Database error: {e}")
        await message.answer("Произошла ошибка при сохранении заявки.")
        return

    # Уведомление администратору
    admin_text = (
        "🚨 Новая заявка в поддержку!\n"
        f"👤 Пользователь: {data['user_id']}\n"
        f"📛 Имя: {data['user_name']}\n"
        f"📧 Email: {data.get('email', 'не указан')}\n"
        f"📝 Сообщение:\n{data['forwarded_text']}\n"
    )
    # Если есть документ, добавляем информацию о нем
    # Отправляем уведомление администратору
    try:
        await message.bot.send_message(chat_id=ADMIN_ID, text=admin_text)

        # Если есть документ, отправляем его администратору
        if data.get('document_path'):
            with open(data['document_path'], 'rb') as doc:
                await message.bot.send_document(chat_id=ADMIN_ID, document=doc)

        # Если есть фото, отправляем его администраторуa
        if data.get('photo_path'):
            with open(data['photo_path'], 'rb') as photo:
                await message.bot.send_photo(chat_id=ADMIN_ID, photo=photo)
    except TelegramAPIError as e:
        logger.error(f"Ошибка отправки уведомления админу: {e}")
        await message.answer("Заявка создана, но не удалось уведомить администратора.")

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


# Обработчик кнопки "Отмена"
async def cancel_handler(callback: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await callback.message.edit_text("Операция отменена.")
    await callback.message.answer(
        "Используйте команду /support, чтобы отправить заявку в техническую поддержку.",
        reply_markup=None  # Убираем клавиатуру
    )
    await callback.answer()