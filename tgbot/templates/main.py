import textwrap
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from .. import callback_datas as calls
from messages.master import *


def error_text(placeholder: str):
    return ERROR_TEXT.format(placeholder=placeholder)


def back_kb(cb: str):
    rows = [[InlineKeyboardButton(text=BTN_BACK_TEXT, callback_data=cb)]]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_kb(confirm_cb: str, cancel_cb: str):
    rows = [[
        InlineKeyboardButton(text=BTN_CONFIRM_TEXT, callback_data=confirm_cb),
        InlineKeyboardButton(text=BTN_CANCEL_TEXT, callback_data=cancel_cb)
    ]]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def destroy_kb():
    rows = [[InlineKeyboardButton(text=BTN_DESTROY_TEXT, callback_data="destroy")]]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def do_action_text(placeholder: str):
    return DO_ACTION_TEXT.format(placeholder=placeholder)


def log_text(title: str, text: str):
    return LOG_TEXT.format(title=title, text=text)


def log_new_mess_kb(username: str):
    rows = [[InlineKeyboardButton(text=BTN_SEND_MESSAGE_TEXT, callback_data=calls.RememberUsername(name=username, do="send_mess").pack())]]
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb


def log_new_deal_kb(username: str, deal_id: str):
    rows = [[
        InlineKeyboardButton(text=BTN_SEND_MESSAGE_TEXT, callback_data=calls.RememberUsername(name=username, do="send_mess").pack()),
        InlineKeyboardButton(text=BTN_COMPLETE_DEAL_TEXT, callback_data=calls.RememberDealId(de_id=deal_id, do="complete").pack()),
        InlineKeyboardButton(text=BTN_REFUND_DEAL_TEXT, callback_data=calls.RememberDealId(de_id=deal_id, do="refund").pack())
    ]]
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb


def log_new_order_kb(username: str, order_id: str):
    # Alias for FunPay order actions, reusing existing deal callbacks.
    return log_new_deal_kb(username, order_id)


def log_new_review_kb(username: str, deal_id: str):
    rows = [[
        InlineKeyboardButton(text=BTN_ANSWER_REVIEW_TEXT, callback_data=calls.RememberDealId(de_id=deal_id, do="answer_rev").pack()),
        InlineKeyboardButton(text=BTN_SEND_MESSAGE_TEXT, callback_data=calls.RememberUsername(name=username, do="send_mess").pack())
    ]]
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb


def sign_text(placeholder: str):
    return SIGN_TEXT.format(placeholder=placeholder)


def call_seller_text(calling_name, chat_link):
    return CALL_SELLER_TEXT.format(calling_name=calling_name, chat_link=chat_link)
