from aiogram.dispatcher.filters.state import State, StatesGroup

# Состояния FSM для администратора
class AdminStates(StatesGroup):
    WAITING_FOR_REPLY = State()