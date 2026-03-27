from aiogram.fsm.state import State, StatesGroup


class GPTReviewStates(StatesGroup):
    waiting_for_text = State()
    waiting_for_int = State()
    waiting_for_message_text = State()
