from aiogram.filters.callback_data import CallbackData


class SkipStep(CallbackData, prefix="skip"):
    step: str


class SelectBot(CallbackData, prefix="select_bot"):
    uuid: str


class ManageBot(CallbackData, prefix="manage_bot"):
    action: str
    uuid: str


class ConfirmDelete(CallbackData, prefix="confirm_delete"):
    uuid: str
    confirmed: bool


class TopUp(CallbackData, prefix="topup"):
    amount: int


class StatsFilter(CallbackData, prefix="stats_filter"):
    period: str
