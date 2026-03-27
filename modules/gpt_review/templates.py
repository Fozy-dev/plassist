from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .helpers import bool_text, mask_secret
from .storage import (
    get_api_base_url,
    get_api_key,
    get_messages,
    get_min_stars,
    get_model,
    get_prompt,
    get_timeout_sec,
    is_enabled,
    is_only_without_reply,
)


def menu_text() -> str:
    return (
        "<b>GPT Review</b>\n\n"
        f"Статус: <b>{bool_text(is_enabled())}</b>\n"
        f"API URL: <code>{get_api_base_url() or 'не задан'}</code>\n"
        f"API key: <code>{mask_secret(get_api_key())}</code>\n"
        f"Модель: <code>{get_model() or 'не задана'}</code>\n"
        f"Мин. оценка: <b>{get_min_stars()}⭐</b>\n"
        f"Только без ответа: <b>{bool_text(is_only_without_reply())}</b>\n"
        f"Таймаут: <b>{get_timeout_sec()} сек.</b>\n\n"
        f"Prompt: <code>{(get_prompt()[:220] + '...') if len(get_prompt()) > 220 else get_prompt()}</code>"
    )


def menu_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Переключить", callback_data="gr_toggle_enabled")
    kb.button(text="API URL", callback_data="gr_edit_api_base_url")
    kb.button(text="API key", callback_data="gr_edit_api_key")
    kb.button(text="Модель", callback_data="gr_edit_model")
    kb.button(text="Мин. оценка", callback_data="gr_edit_min_stars")
    kb.button(text="Только без ответа", callback_data="gr_toggle_only_without_reply")
    kb.button(text="Таймаут", callback_data="gr_edit_timeout")
    kb.button(text="Prompt", callback_data="gr_edit_prompt")
    kb.button(text="Сообщения", callback_data="gr_messages_menu")
    kb.adjust(1, 2, 2, 2, 1, 1)
    return kb.as_markup()


def messages_text() -> str:
    messages = get_messages()
    return (
        "<b>GPT Review • Сообщения</b>\n\n"
        f"admin_log:\n<code>{messages.get('admin_log', '')}</code>\n\n"
        f"reply_failed:\n<code>{messages.get('reply_failed', '')}</code>"
    )


def messages_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="admin_log", callback_data="gr_message:admin_log")
    kb.button(text="reply_failed", callback_data="gr_message:reply_failed")
    kb.button(text="Назад", callback_data="gr_back")
    kb.adjust(1, 1, 1)
    return kb.as_markup()


def edit_message_prompt(message_key: str) -> str:
    return f"<b>GPT Review</b>\n\nОтправьте новый текст для <code>{message_key}</code>."
