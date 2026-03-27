from aiogram.fsm.state import State, StatesGroup


class AutoSmmStates(StatesGroup):
    waiting_for_text = State()
    waiting_for_message_text = State()
