from aiogram.dispatcher.filters.state import State, StatesGroup

# Состояния FSM для пользователя
class SupportStates(StatesGroup):
    GET_CONSENT = State()
    GET_NAME = State()
    GET_EMAIL = State()
    GET_MESSAGE = State()
    GET_FILE = State()
    GET_FILE_UPLOAD = State()
    GET_EMAIL_FORWARDED = State()