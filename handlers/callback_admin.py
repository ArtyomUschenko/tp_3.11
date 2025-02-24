from aiogram import types, Dispatcher, Bot
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils.email_sender import send_email
from utils.database import create_connection
from utils.valid_email import is_valid_email
from date.config import ADMIN_ID, ADMIN_IDS, TELEGRAM_TOKEN
import logging
import os
from aiogram.utils.exceptions import TelegramAPIError

# Настройка логгера
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Путь для временного хранения файлов
TEMP_DIR = "temp_files"
os.makedirs(TEMP_DIR, exist_ok=True)

# Состояния для FSM
class SupportStates(StatesGroup):
    GET_EMAIL_FORWARDED = State()

# Генерация клавиатуры
def get_keyboard(*buttons):
    keyboard = InlineKeyboardMarkup(row_width=len(buttons))
    keyboard.add(*(InlineKeyboardButton(text, callback_data=data) for text, data in buttons))
    return keyboard

# Валидация email
def validate_email(email: str) -> bool:
    return is_valid_email(email)

# Сохранение заявки в базу данных
async def save_request(data: dict):
    conn = await create_connection()
    try:
        await conn.execute(
            """INSERT INTO support_requests 
            (user_id, user_username, name, email, message, admin_id, admin_name, document_path, photo_path) 
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)""",
            data.get('user_id'),
            data.get('user_username'),
            data.get('user_name'),
            data.get('email'),
            data.get('forwarded_text'),
            data.get('admin_id'),
            data.get('admin_name'),
            data.get('document_path'),
            data.get('photo_path')
        )
    finally:
        await conn.close()

# Отправка уведомления администратору
async def notify_admin(message: types.Message, data: dict):
    admin_text = (
        "🚨 Новая заявка в поддержку!\n\n"
        f"👤 Пользователь: {data['user_id']}\n"
        f"📛 Имя: {data['user_name']}\n"
        f"📧 Email: {data.get('email', 'не указан')}\n"
        f"📝 Сообщение:\n{data['forwarded_text']}"
    )
    for admin in ADMIN_IDS:
        try:
            await message.bot.send_message(chat_id=admin, text=admin_text)

            # Отправляем документ, если он есть
            if data.get('document_path'):
                with open(data['document_path'], 'rb') as doc:
                    await message.bot.send_document(chat_id=admin, document=doc, caption="Прикрепленный файл")

            # Отправляем фото, если оно есть
            if data.get('photo_path'):
                with open(data['photo_path'], 'rb') as photo:
                    await message.bot.send_photo(chat_id=admin, photo=photo, caption="Прикрепленное фото")
        except TelegramAPIError as e:
            logger.error(f"Ошибка отправки уведомления админу {admin}: {e}")
            await message.answer(f"Заявка создана, но не удалось уведомить администратора {admin}.")

# Формирование текста письма
def format_email_text(data: dict) -> str:
    return (
        f"Сотрудник ТП завел заявку через чат.<br><br>"
        f"Имя: <b>{data['user_name']}</b><br>"
        f"Email: <b>{data.get('email', 'не указан')}</b><br>"
        f"ID пользователя: <b>{data['user_id']}</b><br>"
        f"Ссылка в tg: <a href='https://t.me/{data['user_username']}'>https://t.me/{data['user_username']}</a><br>"
        f"Текст обращения: <b>{data['forwarded_text']}</b><br><br>"
        f"Сообщение переслал сотрудник ТП:<br>"
        f"ID: <b>{data['admin_id']}</b><br>"
        f"Имя: <b>{data['admin_name']}</b>"
    )

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
        "document_path": None,
        "photo_path": None
    }

    # Проверяем, содержит ли сообщение документ или фото
    if message.document:
        user_data["document_path"] = await download_file(message.document.file_id, "document")
        logger.info(f"Document detected: {user_data['document_path']}")
    elif message.photo:
        user_data["photo_path"] = await download_file(message.photo[-1].file_id, "photo")
        logger.info(f"Photo detected: {user_data['photo_path']}")

    # Сохраняем данные в FSM
    await state.update_data(**user_data)

    # Запрашиваем email пользователя
    await message.answer(
        "Введите email пользователя (или нажмите 'Пропустить'):",
        reply_markup=get_keyboard(("❌ Отмена", "cancel"), ("⏭ Пропустить", "skip_email"))
    )
    await SupportStates.GET_EMAIL_FORWARDED.set()

# Обработчик кнопки "Пропустить"
async def skip_email(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(email=None)
    await process_forwarded_request(callback.message, state)

# Обработчик email
async def get_forwarded_email(message: types.Message, state: FSMContext):
    email = message.text.strip()
    if email and not validate_email(email):
        await message.answer("❌ Некорректный email. Попробуйте еще раз:")
        return

    await state.update_data(email=email)
    await process_forwarded_request(message, state)

# Обработка заявки
async def process_forwarded_request(message: types.Message, state: FSMContext):
    data = await state.get_data()

    # Сохраняем заявку в БД
    await save_request(data)

    # Уведомление администратору
    await notify_admin(message, data)

    # Отправляем письмо
    # Формируем список вложений
    attachments = []
    if data.get('document_path'):
        attachments.append(data['document_path'])
    if data.get('photo_path'):
        attachments.append(data['photo_path'])

    # Отправляем письмо с вложениями
    email_text = format_email_text(data)
    send_email(
        subject="Вопрос от пользователя через чат ГИС “Платформа “ЦХЭД”",
        body=email_text,
        is_html=True,
        attachments=attachments
    )

    await message.answer("Ваша заявка отправлена. Спасибо!")
    await state.finish()

# Обработчик кнопки "Отмена"
async def cancel_handler(callback: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await callback.message.edit_text("Операция отменена.")
    await callback.message.answer(
        "Используйте команду /support, чтобы отправить заявку в техническую поддержку.",
        reply_markup=None
    )
    await callback.answer()

# Функция для скачивания файла
bot = Bot(token=TELEGRAM_TOKEN)
async def download_file(file_id: str, file_type: str) -> str:
    """Скачивает и сохраняет файл из Telegram"""
    try:
        file_path = f"{TEMP_DIR}/{file_id}_{file_type}"
        file = await bot.get_file(file_id)
        await file.download(destination_file=file_path)
        logger.info(f"File downloaded: {file_path}")
        return file_path
    except Exception as e:
        logger.error(f"File download error: {e}")
        return None


