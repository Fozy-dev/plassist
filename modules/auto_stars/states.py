from aiogram.fsm.state import State, StatesGroup


class AutoStarsStates(StatesGroup):
    waiting_for_message_text = State()
    waiting_for_setting_value = State()
