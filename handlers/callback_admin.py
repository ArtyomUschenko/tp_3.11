from aiogram import types, Dispatcher, Bot
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils.email_sender import send_email
from utils.database import create_connection
from utils.valid_email import is_valid_email
from date.config import ADMIN_ID, ADMIN_IDS, TELEGRAM_TOKEN
import logging
import os, re
from aiogram.utils.exceptions import TelegramAPIError
import aiohttp
import datetime

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

    # Проверяем, содержит ли сообщение документ (например, PDF)
    if message.document:
        logger.info(
            f"Document detected: file_id={message.document.file_id}, mime_type={message.document.mime_type}, file_name={message.document.file_name}"
        )
        # Скачиваем документ с оригинальным именем
        original_name = message.document.file_name or "document"
        file_path = await download_file(
            message.document.file_id,
            "document",
            original_name
        )
        if file_path:
            user_data["document_path"] = file_path
            logger.info(f"Document saved: {user_data['document_path']}")
        else:
            logger.error("Failed to download document")
            await message.answer("Не удалось скачать прикрепленный документ.")

    # Проверяем, содержит ли сообщение фото
    elif message.photo:
        logger.info(f"Photo detected: file_id={message.photo[-1].file_id}")
        # Для фото генерируем имя, так как file_name недоступно
        original_name = f"photo_{message.photo[-1].file_id[:8]}"
        file_path = await download_file(
            message.photo[-1].file_id,
            "photo",
            original_name
        )
        if file_path:
            user_data["photo_path"] = file_path
            logger.info(f"Photo saved: {user_data['photo_path']}")
        else:
            logger.error("Failed to download photo")
            await message.answer("Не удалось скачать прикрепленное фото.")

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
    try:
        data = await state.get_data()

        # Сохраняем заявку в БД
        await save_request(data)

        # Уведомление администратору
        await notify_admin(message, data)

        # Отправляем письмо
        # Формируем список вложений
        attachments = []
        if data.get('document_path') and os.path.exists(data['document_path']):
            attachments.append(data['document_path'])
            logger.info(f"Adding document to attachments: {data['document_path']}")
        if data.get('photo_path') and os.path.exists(data['photo_path']):
            attachments.append(data['photo_path'])
            logger.info(f"Adding photo to attachments: {data['photo_path']}")

        # Отправляем письмо с вложениями
        email_text = format_email_text(data)
        send_email(
            subject="Вопрос от пользователя через чат ГИС “Платформа “ЦХЭД”",
            body=email_text,
            is_html=True,
            attachments=attachments
        )

        await message.answer("Ваша заявка отправлена. Спасибо!")

        # Очистка временных файлов
        logger.info(f"Отправка вложений: {attachments}")
        for file_path in attachments:
            logger.info(f"Имя файла: {os.path.basename(file_path)}")
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.info(f"Удален временный файл: {file_path}")
            except Exception as e:
                logger.error(f"Ошибка удаления файла: {str(e)}")
    finally:
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


async def download_file(file_id: str, file_type: str, original_name: str = None) -> str:
    """Скачивает и сохраняет файл из Telegram с правильным именем"""
    try:
        # Генерируем временную метку
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        # Получаем информацию о файле
        file = await bot.get_file(file_id)
        file_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file.file_path}"

        # Определяем базовое имя файла
        if original_name:
            # Убираем запрещенные символы в имени файла
            clean_name = re.sub(r'[\\/*?:"<>|]', "", original_name)
            base_name = f"{timestamp}_{clean_name}"
        else:
            # Извлекаем расширение из file_path
            ext = os.path.splitext(file.file_path)[1] if '.' in file.file_path else ''
            # Формируем имя по шаблону: тип_дата_часть_id
            base_name = f"{file_type}_{timestamp}_{file_id[:8]}{ext}"

        file_path = os.path.join(TEMP_DIR, base_name)

        # Скачиваем файл
        async with aiohttp.ClientSession() as session:
            async with session.get(file_url) as response:
                if response.status == 200:
                    content = await response.read()
                    with open(file_path, 'wb') as f:
                        f.write(content)
                    logger.info(f"Файл сохранен как: {file_path}")
                    return file_path
                logger.error(f"Ошибка загрузки: {response.status}")
        return None
    except Exception as e:
        logger.error(f"Ошибка загрузки файла: {str(e)}")
        return None

