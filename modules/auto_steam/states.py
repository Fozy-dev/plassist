from aiogram.fsm.state import State, StatesGroup


class AutoSteamStates(StatesGroup):
    waiting_for_text = State()
    waiting_for_int = State()
    waiting_for_float = State()
    waiting_for_message_text = State()
