from aiogram import types, Bot
from aiogram.dispatcher import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils.email_sender import send_email
from utils.valid_email import is_valid_email
from utils.database import create_connection
from date.config  import ADMIN_ID,  TELEGRAM_TOKEN, ADMIN_IDS
from states import user_state, admin_state
from keyboards import inline
from aiogram.utils.exceptions import TelegramAPIError
import logging
import datetime
import aiohttp
import os, re

# Настройка логгера
logging.basicConfig(level=logging.INFO)

# Настройка логгера
logger = logging.getLogger(__name__)

# Путь для временного хранения файлов
TEMP_DIR = "temp_files"
os.makedirs(TEMP_DIR, exist_ok=True)

# Текст согласия (используется HTML-форматирование)
CONSENT_TEXT = (
    "Вы даете согласие на обработку персональных данных?\n\n"
    "[Политика в отношении обработки и защиты персональных данных]"
    "(https://platform-eadsc.voskhod.ru/docs_back/personal_data_processing_policy.pdf)"
)
def create_consent_keyboard():
    return InlineKeyboardMarkup(row_width=2).add(
        InlineKeyboardButton("✅ Согласен", callback_data="consent_yes"),
        InlineKeyboardButton("❌ Отмена", callback_data="cancel")
    )

# Уведомление администратору
async def send_admin_notification(bot, user_data, user_id, username, problem,  document_path=None, photo_path=None):
    admin_text = (
        "🚨 Новая заявка в поддержку!\n"
        f"👤 Пользователь: {user_id}\n"
        f"👤 Ссылка в tg: @{username or 'Не указан'}\n"
        f"📛 Имя: {user_data['name']}\n"
        f"📧 Email: {user_data['email']}\n"
        f"📝 Сообщение:\n{problem}"
    )

    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(InlineKeyboardButton("✉️ Ответить", callback_data=f"reply_{user_id}"))
    # try:
    #     await bot.send_message(ADMIN_ID, admin_text, reply_markup=keyboard)
    #     logging.info("Уведомление администратору отправлено")
    # except Exception as e:
    #     logging.error(f"Уведомление не отправлено администратору: {e}")


    for admin in ADMIN_IDS:
        try:
            await bot.send_message(chat_id=admin, text=admin_text, reply_markup=keyboard)

            # Отправляем документ, если он есть
            if document_path:
                with open(document_path, 'rb') as doc:
                    await bot.send_document(chat_id=admin, document=doc, caption="Прикрепленный файл")
            # Отправляем фото, если оно есть
            if photo_path:
                with open(photo_path, 'rb') as photo:
                    await bot.send_photo(chat_id=admin, photo=photo, caption="Прикрепленное фото")
        except TelegramAPIError as e:
            logger.error(f"Ошибка отправки уведомления админу {admin}: {e}")



# Отправка email
async def send_confirmation_email(user_data, user_id, username, problem):
    email_text = (
        f"Пользователь оставил запрос в техническую поддержку через чат.<br><br>"
        f"Имя: <b>{user_data['name']}</b><br>"
        f"Email: <b>{user_data['email']}</b><br>"
        f"ID пользователя: <b>{user_id}</b><br>"
        f"Ссылка в tg: <b>https://t.me/{username or 'Не_указан'}</b><br>"
        f"Текст обращения: <b>{problem}</b>"
    )
    try:
        send_email("Вопрос от пользователя через чат ГИС “Платформа “ЦХЭД”", body=email_text, is_html=True)
        logging.info("Заявка отправлена на почту")
    except Exception as e:
        logging.error(f"Ошибка отправки заявки на почту: {e}")

# Сохранение информации в БД
async def save_to_database(user_id, user_data, username, problem, document_path=None, photo_path=None):
    conn = await create_connection()
    try:
        await conn.execute(
            """INSERT INTO support_requests 
            (user_id, name, user_username, email, message, document_path, photo_path) 
            VALUES ($1, $2, $3, $4, $5, $6, $7)""",
            user_id, user_data['name'], username, user_data['email'],
            problem, document_path, photo_path
        )
    finally:
        await conn.close()

# Начало заполнения заявки
async def start_support(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer(CONSENT_TEXT, reply_markup=create_consent_keyboard(), parse_mode=types.ParseMode.MARKDOWN)
    await state.set_state(user_state.SupportStates.GET_CONSENT.state)


async def handle_consent(callback: types.CallbackQuery, state: FSMContext):
    if callback.data == "consent_yes":
        await callback.message.edit_text("Пожалуйста, введите ваше имя:", reply_markup=inline.cancel_keyboard_support())
        await state.set_state(user_state.SupportStates.GET_NAME.state)
    else:
        await cancel_handler(callback, state)
        await callback.answer()

async def get_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Введите ваш email:", reply_markup=inline.get_back_cancel_keyboard())
    await state.set_state(user_state.SupportStates.GET_EMAIL.state)

async def get_email(message: types.Message, state: FSMContext):
    if not is_valid_email(message.text):
        await message.answer("Некорректный email. Пожалуйста, введите email еще раз.")
        return

    await state.update_data(email=message.text)
    await message.answer("Опишите вашу проблему:", reply_markup=inline.get_back_cancel_keyboard())
    await state.set_state(user_state.SupportStates.GET_MESSAGE.state)

async def get_message(message: types.Message, state: FSMContext):
    # Сохраняем временную информацию о проблеме
    await state.update_data(problem=message.text)
    await message.answer("Хотите прикрепить файл к заявке?", reply_markup=inline.get_yes_no_keyboard_support())
    await state.set_state(user_state.SupportStates.GET_FILE.state)

async def handle_file_choice(callback: types.CallbackQuery, state: FSMContext):
    if callback.data == "no_support":
        await process_support_request(callback, state)
    else:
        await callback.message.edit_text("Пожалуйста, отправьте файл или фото.")
        await state.set_state(user_state.SupportStates.GET_FILE_UPLOAD.state)
    await callback.answer()


async def process_support_request(callback: types.CallbackQuery, state: FSMContext):
    # Извлекаем основные данные пользователя из сообщения
    user_data = await state.get_data()
    user_id = callback.from_user.id
    username = callback.from_user.username
    problem = user_data.get("problem")
    document_path = user_data.get("document_path")
    photo_path = user_data.get("photo_path")
    try:
        # Сохранение в базу данных
        await save_to_database(user_id, user_data, username, problem, document_path, photo_path)

        # Уведомление администратора
        await send_admin_notification(
            callback.message.bot,
            user_data,
            user_id,
            username,
            problem,
            document_path,
            photo_path
        )

        # Отправка email
        await send_confirmation_email(user_data, user_id, username, problem)

        await callback.message.edit_text("Ваша заявка отправлена. Спасибо!")
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        await callback.message.edit_text("Ошибка при отправке заявки. Попробуйте снова.")
    finally:
        await state.finish()

# Обработчик кнопки "Назад"
async def back_handler(callback: types.CallbackQuery, state: FSMContext):
    state_mapping = {
        user_state.SupportStates.GET_EMAIL.state:
            ("Пожалуйста, введите ваше имя:", user_state.SupportStates.GET_NAME),
        user_state.SupportStates.GET_MESSAGE.state:
            ("Введите ваш email:", user_state.SupportStates.GET_EMAIL)
    }

    current_state = await state.get_state()
    if current_state in state_mapping:
        text, new_state = state_mapping[current_state]
        await callback.message.edit_text(text, reply_markup=inline.get_back_cancel_keyboard())
        await new_state.set()
    await callback.answer()

# Обработчик кнопки "Отмена"
async def cancel_handler(callback: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await callback.message.edit_text("Операция отменена.")
    await callback.message.answer(
        "Используйте команду /support, чтобы отправить заявку в техническую поддержку.",
        reply_markup=None  # Убираем клавиатуру
    )
    await callback.answer()

# Отправка сообщения пользователю через ТГ
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
    finally:
        await state.finish()





#
#
#
#
#
#
# # Функция для скачивания файла
# bot = Bot(token=TELEGRAM_TOKEN)
#
# async def download_file(file_id: str, file_type: str, original_name: str = None) -> str:
#     """Скачивает и сохраняет файл из Telegram с правильным именем"""
#     try:
#         # Генерируем временную метку
#         timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
#
#         # Получаем информацию о файле
#         file = await bot.get_file(file_id)
#         file_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file.file_path}"
#
#         # Определяем базовое имя файла
#         if file_type == "document" and original_name:
#             # Убираем запрещенные символы в имени файла для документов
#             clean_name = re.sub(r'[\\/*?:"<>|]', "", original_name)
#             base_name = f"{timestamp}_{clean_name}"
#         elif file_type == "photo":
#             # Для фото добавляем расширение .jpg
#             clean_name = re.sub(r'[\\/*?:"<>|]', "", original_name or f"photo_{file_id[:8]}")
#             base_name = f"{timestamp}_{clean_name}.jpg"
#         else:
#             # Извлекаем расширение из file_path, если есть
#             ext = os.path.splitext(file.file_path)[1] if '.' in file.file_path else ''
#             base_name = f"{file_type}_{timestamp}_{file_id[:8]}{ext}"
#
#         file_path = os.path.join(TEMP_DIR, base_name)
#
#         # Скачиваем файл
#         async with aiohttp.ClientSession() as session:
#             async with session.get(file_url) as response:
#                 if response.status == 200:
#                     content = await response.read()
#                     with open(file_path, 'wb') as f:
#                         f.write(content)
#                     logger.info(f"Файл сохранен как: {file_path}")
#                     return file_path
#                 logger.error(f"Ошибка загрузки: {response.status}")
#         return None
#     except Exception as e:
#         logger.error(f"Ошибка загрузки файла: {str(e)}")
#         return None
#
#
#
# from aiogram import types
# from aiogram.dispatcher import FSMContext
#
# async def upload_file(message: types.Message, state: FSMContext):
#     # Проверяем тип отправленного сообщения (документ или фото)
#     if message.document:
#         file_id = message.document.file_id
#         file_name = message.document.file_name
#         file_type = "document"
#     elif message.photo:
#         file_id = message.photo[-1].file_id
#         file_name = None  # Для фото имя файла неизвестно
#         file_type = "photo"
#     else:
#         await message.answer("Пожалуйста, отправьте файл или фото.")
#         return
#
#     # Скачиваем файл
#     file_path = await download_file(file_id, file_type, file_name)
#     if not file_path:
#         await message.answer("Произошла ошибка при загрузке файла. Попробуйте снова.")
#         return
#
#     # Сохраняем путь к файлу в состоянии пользователя
#     await state.update_data(document_path=file_path)
#
#     # Переходим к обработке заявки
#     await process_support_request(message, state)