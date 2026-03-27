from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from .meta import NAME
from .helpers import max_price_text, ratings_summary, status_text
from .storage import get_max_price, get_messages, get_ratings, get_refunded_orders, is_enabled, is_notify_buyer_enabled


def menu_text() -> str:
    ratings = get_ratings()
    return (
        f"<b>{NAME}</b>\n\n"
        f"Статус: {status_text(is_enabled())}\n"
        f"Оценки для возврата: {ratings_summary(ratings)}\n"
        f"Максимальная сумма: {max_price_text(get_max_price())}\n"
        f"Сообщение покупателю: {'включено' if is_notify_buyer_enabled() else 'выключено'}\n"
        f"Выполнено возвратов: {len(get_refunded_orders())}"
    )


def menu_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=("Выключить" if is_enabled() else "Включить"), callback_data="ar_toggle_enabled")],
        [InlineKeyboardButton(text="Оценки", callback_data="ar_ratings_menu")],
        [InlineKeyboardButton(text="Макс. сумма", callback_data="ar_edit_max_price")],
        [InlineKeyboardButton(text=("Выключить сообщение" if is_notify_buyer_enabled() else "Включить сообщение"), callback_data="ar_toggle_notify")],
        [InlineKeyboardButton(text="Сообщения", callback_data="ar_messages_menu")],
        [InlineKeyboardButton(text="Назад", callback_data="destroy")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def ratings_text() -> str:
    ratings = get_ratings()
    return (
        "<b>AutoRefund - оценки</b>\n\n"
        f"1⭐: {'включено' if ratings.get('1') else 'выключено'}\n"
        f"2⭐: {'включено' if ratings.get('2') else 'выключено'}\n"
        f"3⭐: {'включено' if ratings.get('3') else 'выключено'}\n"
        f"4⭐: {'включено' if ratings.get('4') else 'выключено'}\n"
        f"5⭐: {'включено' if ratings.get('5') else 'выключено'}"
    )


def ratings_kb() -> InlineKeyboardMarkup:
    ratings = get_ratings()
    rows = []
    for stars in range(1, 6):
        state = "ON" if ratings.get(str(stars)) else "OFF"
        rows.append([InlineKeyboardButton(text=f"{stars}⭐ {state}", callback_data=f"ar_toggle_rating:{stars}")])
    rows.append([InlineKeyboardButton(text="Назад", callback_data="ar_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def messages_text() -> str:
    messages = get_messages()
    return (
        "<b>AutoRefund - сообщения</b>\n\n"
        f"refund_sent:\n<blockquote>{messages.get('refund_sent', '')}</blockquote>\n\n"
        f"admin_log:\n<blockquote>{messages.get('admin_log', '')}</blockquote>\n\n"
        f"refund_failed:\n<blockquote>{messages.get('refund_failed', '')}</blockquote>"
    )


def messages_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="refund_sent", callback_data="ar_message:refund_sent")],
        [InlineKeyboardButton(text="admin_log", callback_data="ar_message:admin_log")],
        [InlineKeyboardButton(text="refund_failed", callback_data="ar_message:refund_failed")],
        [InlineKeyboardButton(text="Назад", callback_data="ar_back")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def edit_message_prompt(message_key: str) -> str:
    return f"Отправьте новый текст для <code>{message_key}</code>."
