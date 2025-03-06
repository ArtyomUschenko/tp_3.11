import os
import re
import logging
import datetime
import aiohttp
from typing import Optional
from aiogram import types, Bot
from aiogram.dispatcher import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils.email_sender import send_email
from utils.valid_email import is_valid_email
from utils.database import create_connection
from date.config import ADMIN_IDS, TELEGRAM_TOKEN
from states import user_state, admin_state
from keyboards import inline

# Константы
TEMP_DIR = "temp_files"
os.makedirs(TEMP_DIR, exist_ok=True)

CONSENT_TEXT = (
    "Вы даете согласие на обработку персональных данных?\n\n"
    "[Политика в отношении обработки и защиты персональных данных]"
    "(https://platform-eadsc.voskhod.ru/docs_back/personal_data_processing_policy.pdf)"
)

# Настройка логгера
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация бота
bot = Bot(token=TELEGRAM_TOKEN)

# Утилиты
def create_consent_keyboard() -> InlineKeyboardMarkup:
    # Создает клавиатуру с вариантами согласия на обработку данных
    return InlineKeyboardMarkup(row_width=2).add(
        InlineKeyboardButton("✅ Согласен", callback_data="consent_yes"),
        InlineKeyboardButton("❌ Отмена", callback_data="cancel")
    )

def sanitize_filename(filename: str) -> str:
    # Очищает имя файла от недопустимых символов
    return re.sub(r'[\\/*?:"<>|]', "_", filename)


# Обработка данных
async def save_support_request(user_id: int, user_data: dict, username: str, problem: str,
                               document_path: Optional[str] = None) -> None:
    # Сохраняет данные в базу данных
    conn = await create_connection()
    try:
        await conn.execute(
            "INSERT INTO support_requests (user_id, name, user_username, email, message, document_path) "
            "VALUES ($1, $2, $3, $4, $5, $6)",
            user_id, user_data['name'], username, user_data['email'], problem, document_path
        )
    except Exception as e:
        logger.error(f"Ошибка сохранения в БД: {e}")
        raise
    finally:
        await conn.close()


async def notify_admins(bot: Bot, user_data: dict, user_id: int, username: str, problem: str,
                        document_path: Optional[str] = None) -> None:
    # Уведомляет администраторов о новой заявке
    admin_text = (
        f"🚨 Новая заявка в поддержку!\n"
        f"👤 Пользователь: {user_id}\n"
        f"👤 Ссылка в tg: @{username or 'Не указан'}\n"
        f"📛 Имя: {user_data['name']}\n"
        f"📧 Email: {user_data['email']}\n"
        f"📝 Сообщение:\n{problem}"
    )
    keyboard = InlineKeyboardMarkup(row_width=1).add(
        InlineKeyboardButton("✉️ Ответить", callback_data=f"reply_{user_id}")
    )
    for admin in ADMIN_IDS:
        try:
            await bot.send_message(admin, admin_text, reply_markup=keyboard)
            if document_path:
                with open(document_path, 'rb') as file:
                    await bot.send_document(admin, file)
            logger.info(f"Уведомление отправлено администратору {admin}")
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления администратору {admin}: {e}")


async def send_email_confirmation(user_data: dict, user_id: int, username: str, problem: str,
                                  document_path: Optional[str] = None) -> None:
    # Отправляет email с подтверждением заявки
    email_text = (
        f"Пользователь оставил запрос в техническую поддержку через чат.<br><br>"
        f"Имя: <b>{user_data['name']}</b><br>"
        f"Email: <b>{user_data['email']}</b><br>"
        f"ID пользователя: <b>{user_id}</b><br>"
        f"Ссылка в tg: <b>https://t.me/{username or 'Не_указан'}</b><br>"
        f"Текст обращения: <b>{problem}</b>"
    )
    attachments = [document_path] if document_path else None
    try:
        send_email("Вопрос от пользователя через чат ГИС “Платформа “ЦХЭД”", body=email_text, is_html=True,
                   attachments=attachments)
        logger.info("Email с подтверждением отправлен")
    except Exception as e:
        logger.error(f"Ошибка отправки email: {e}")
        raise


async def download_file(file_id: str, file_type: str, original_name: Optional[str] = None) -> Optional[str]:
    # Скачивает файл из Telegram и сохраняет его локально
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    try:
        file = await bot.get_file(file_id)
        file_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file.file_path}"

        if file_type == "document" and original_name:
            clean_name = sanitize_filename(original_name)
            base_name = f"{timestamp}_{clean_name}"
        elif file_type == "photo":
            clean_name = sanitize_filename(original_name or f"photo_{file_id[:8]}")
            base_name = f"{timestamp}_{clean_name}.jpg"
        else:
            ext = os.path.splitext(file.file_path)[1] if '.' in file.file_path else ''
            base_name = f"{file_type}_{timestamp}_{file_id[:8]}{ext}"

        file_path = os.path.join(TEMP_DIR, base_name)
        async with aiohttp.ClientSession() as session:
            async with session.get(file_url) as response:
                if response.status == 200:
                    content = await response.read()
                    with open(file_path, 'wb') as f:
                        f.write(content)
                    logger.info(f"Файл сохранен: {file_path}")
                    return file_path
                logger.error(f"Ошибка загрузки файла, статус: {response.status}")
                return None
    except Exception as e:
        logger.error(f"Ошибка при скачивании файла: {e}")
        return None


# Обработка заявок
async def process_support_request(message_or_callback: types.Message | types.CallbackQuery, state: FSMContext) -> None:
    # Обрабатывает заявку на поддержку
    user_data = await state.get_data()
    user_id = message_or_callback.from_user.id
    username = message_or_callback.from_user.username
    problem = user_data.get("problem")
    document_path = user_data.get("document_path")
    bot_instance = message_or_callback.bot

    try:
        await save_support_request(user_id, user_data, username, problem, document_path)
        await notify_admins(bot_instance, user_data, user_id, username, problem, document_path)
        await send_email_confirmation(user_data, user_id, username, problem, document_path)

        if isinstance(message_or_callback, types.CallbackQuery):
            await message_or_callback.message.edit_text("Ваша заявка отправлена. Спасибо!")
        else:
            await message_or_callback.answer("Ваша заявка отправлена. Спасибо!")
    except Exception as e:
        logger.error(f"Ошибка обработки заявки: {e}")
        error_message = "Ошибка при отправке заявки. Попробуйте снова."
        if isinstance(message_or_callback, types.CallbackQuery):
            await message_or_callback.message.edit_text(error_message)
        else:
            await message_or_callback.answer(error_message)
    finally:
        await state.finish()


# Обработчики пользовательских действий
async def start_support(callback: types.CallbackQuery, state: FSMContext) -> None:
    # Начинает процесс заполнения заявки
    await callback.answer()
    await callback.message.answer(CONSENT_TEXT, reply_markup=create_consent_keyboard(),
                                  parse_mode=types.ParseMode.MARKDOWN)
    await state.set_state(user_state.SupportStates.GET_CONSENT)


async def handle_consent(callback: types.CallbackQuery, state: FSMContext) -> None:
    # Обрабатывает выбор пользователя по согласию на обработку данных
    if callback.data == "consent_yes":
        await callback.message.edit_text("Пожалуйста, введите ваше имя:", reply_markup=inline.cancel_keyboard_support())
        await state.set_state(user_state.SupportStates.GET_NAME)
    else:
        await cancel_handler(callback, state)
    await callback.answer()


async def get_name(message: types.Message, state: FSMContext) -> None:
    # Получает имя пользователя и переходит к следующему шагу
    await state.update_data(name=message.text)
    await message.answer("Введите ваш email:", reply_markup=inline.get_back_cancel_keyboard())
    await state.set_state(user_state.SupportStates.GET_EMAIL)


async def get_email(message: types.Message, state: FSMContext) -> None:
    try:
        # Проверяем email на корректность
        is_valid, error_message = is_valid_email(message.text)

        if not is_valid:
            logger.info(f"Некорректный email: {message.text}. Причина: {error_message}")
            await message.answer(
                f"❌ {error_message}\nПожалуйста, введите корректный email:",
                reply_markup=inline.get_back_cancel_keyboard()
            )
            return

        # Если email корректный, сохраняем его и переходим к следующему шагу
        logger.info(f"Email прошел валидацию: {message.text}")
        await state.update_data(email=message.text.strip().lower())
        await message.answer(
            "Опишите вашу проблему:",
            reply_markup=inline.get_back_cancel_keyboard()
        )
        await state.set_state(user_state.SupportStates.GET_MESSAGE)

    except Exception as e:
        logger.error(f"Ошибка при обработке email: {e}")
        await message.answer(
            "Произошла ошибка при проверке email. Пожалуйста, попробуйте еще раз:",
            reply_markup=inline.get_back_cancel_keyboard()
        )

async def get_message(message: types.Message, state: FSMContext) -> None:
    # Получает сообщение пользователя и переходит к следующему шагу
    await state.update_data(problem=message.text)
    await message.answer("Хотите прикрепить файл к заявке?", reply_markup=inline.get_yes_no_keyboard_support())
    await state.set_state(user_state.SupportStates.GET_FILE)


async def handle_file_choice(callback: types.CallbackQuery, state: FSMContext) -> None:
    # Обрабатывает выбор пользователя по прикреплению файла
    if callback.data == "no_support":
        await process_support_request(callback, state)
    else:
        await callback.message.edit_text("Пожалуйста, отправьте файл или фото.")
        await state.set_state(user_state.SupportStates.GET_FILE_UPLOAD)
    await callback.answer()


async def upload_file(message: types.Message, state: FSMContext) -> None:
    # Обрабатывает загрузку файла от пользователя
    logger.info(f"Получено сообщение в состоянии GET_FILE_UPLOAD от {message.from_user.id}")

    if message.document:
        file_id, file_type, original_name = message.document.file_id, "document", message.document.file_name
        logger.info(f"Обработка документа: {original_name}")
    elif message.photo:
        file_id, file_type, original_name = message.photo[-1].file_id, "photo", None
        logger.info("Обработка фото")
    else:
        logger.warning(f"Сообщение не содержит документ или фото: {message.content_type}")
        await message.answer("Пожалуйста, отправьте файл или фото.")
        return

    file_path = await download_file(file_id, file_type, original_name)
    if not file_path:
        logger.error("Не удалось скачать файл")
        await message.answer("Ошибка при загрузке файла. Попробуйте снова.")
        return

    await state.update_data(document_path=file_path)
    logger.info(f"Файл сохранен, путь: {file_path}, обработка заявки начинается")
    await process_support_request(message, state)


# Обработчики администратора
async def handle_admin_callback(callback: types.CallbackQuery, state: FSMContext) -> None:
    # Обрабатывает запросы от администратора
    action, data = callback.data.split("_")
    if action == "reply":
        await state.update_data(target_user_id=data)
        await callback.message.answer("Введите ваш ответ:")
        await admin_state.AdminStates.WAITING_FOR_REPLY.set()
    elif action == "view":
        await callback.answer("Заявка будет показана здесь", show_alert=True)
    await callback.answer()


async def handle_admin_reply(message: types.Message, state: FSMContext) -> None:
    # Обрабатывает ответ администратора на заявку
    user_data = await state.get_data()
    target_user_id = user_data.get("target_user_id")
    try:
        await message.bot.send_message(target_user_id, f"📨 Ответ от поддержки:\n\n{message.text}")
        await message.answer("✅ Ответ успешно отправлен!")
    except Exception as e:
        await message.answer("❌ Ошибка отправки ответа")
        logger.error(f"Ошибка отправки ответа: {e}")
    finally:
        await state.finish()


# Общие обработчики
async def back_handler(callback: types.CallbackQuery, state: FSMContext) -> None:
    # Обрабатывает кнопку "Назад"
    current_state = await state.get_state()
    logger.info(f"Обработка кнопки 'Назад' из состояния: {current_state}")

    # Маппинг состояний и их обработчиков
    state_handlers = {
        'SupportStates:GET_EMAIL': {
            'target_state': user_state.SupportStates.GET_NAME,
            'message': "Пожалуйста, введите ваше имя:",
            'keyboard': inline.cancel_keyboard_support()
        },
        'SupportStates:GET_MESSAGE': {
            'target_state': user_state.SupportStates.GET_EMAIL,
            'message': "Введите ваш email:",
            'keyboard': inline.get_back_cancel_keyboard()
        },
        'SupportStates:GET_FILE': {
            'target_state': user_state.SupportStates.GET_MESSAGE,
            'message': "Опишите вашу проблему:",
            'keyboard': inline.get_back_cancel_keyboard()
        }
    }

    try:
        if current_state in state_handlers:
            handler = state_handlers[current_state]
            # Сохраняем текущие данные
            current_data = await state.get_data()
            # Устанавливаем новое состояние
            await handler['target_state'].set()
            # Восстанавливаем данные в новом состоянии
            await state.update_data(**current_data)
            # Обновляем сообщение
            await callback.message.edit_text(
                handler['message'],
                reply_markup=handler['keyboard']
            )
            logger.info(f"Переход из {current_state} в состояние: {handler['target_state'].state}")
        else:
            logger.warning(f"Неожиданное состояние для кнопки 'Назад': {current_state}")
            await callback.answer("Действие недоступно в текущем состоянии")
            return

    except Exception as e:
        logger.error(f"Ошибка при обработке кнопки 'Назад': {e}")
        await callback.answer("Произошла ошибка. Попробуйте отменить и начать заново.")
        return

    await callback.answer()


async def cancel_handler(callback: types.CallbackQuery, state: FSMContext) -> None:
    # Обрабатывает кнопку "Отмена"
    await state.finish()
    await callback.message.edit_text("Операция отменена.")
    await callback.message.answer("Используйте команду /start, чтобы отправить заявку в техническую поддержку.")
    await callback.answer()
