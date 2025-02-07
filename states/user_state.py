from aiogram.dispatcher.filters.state import State, StatesGroup

# Состояния FSM для пользователя
class SupportStates(StatesGroup):
    GET_CONSENT = State() # Новое состояние для запроса согласия
    GET_NAME = State()
    GET_EMAIL = State()
    GET_MESSAGE = State()
    GET_EMAIL_FORWARDED = State()  # Новое состояние для пересланных сообщений