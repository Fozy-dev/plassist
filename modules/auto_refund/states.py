from aiogram.fsm.state import State, StatesGroup


class AutoRefundStates(StatesGroup):
    waiting_for_max_price = State()
    waiting_for_message_text = State()
