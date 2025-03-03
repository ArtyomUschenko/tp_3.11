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

# Настройка логгера
logger = logging.getLogger(__name__)

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
async def send_admin_notification(bot, user_data, user_id, username, problem):
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
    for admin in ADMIN_IDS:
        try:
            await bot.send_message(admin, admin_text, reply_markup=keyboard)
            logging.info("Уведомление администратору отправлено")
        except Exception as e:
            logging.error(f"Уведомление не отправлено администратору: {e}")

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
async def save_to_database(user_id, user_data, username, problem, document_path=None):
    conn = await create_connection()
    try:
        await conn.execute(
            """INSERT INTO support_requests 
            (user_id, name, user_username, email, message, document_path) 
            VALUES ($1, $2, $3, $4, $5, $6)""",
            user_id, user_data['name'], username, user_data['email'],
            problem, document_path
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
    user_data = await state.get_data()
    user_id = callback.from_user.id
    username = callback.from_user.username
    problem = user_data.get("problem")
    try:
        # Сохранение в базу данных
        await save_to_database(user_id, user_data, username, problem)

        # Уведомление администратора
        await send_admin_notification(
            callback.message.bot,
            user_data,
            user_id,
            username,
            problem
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



