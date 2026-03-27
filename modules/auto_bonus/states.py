from aiogram.fsm.state import State, StatesGroup


class AutoBonusStates(StatesGroup):
    waiting_for_target = State()
    waiting_for_bonus_text = State()
    waiting_for_message_text = State()
