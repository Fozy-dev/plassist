from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from .meta import NAME
from .storage import get_allowed_quantities, get_config, get_messages, get_today_stats


def menu_text() -> str:
    config = get_config()
    stats = get_today_stats()
    success = int(stats.get("successful_transactions", 0))
    failed = int(stats.get("unsuccessful_transactions", 0))
    fragment = config.get("fragment_api") or {}
    ton = config.get("ton") or {}
    return (
        f"<b>{NAME}</b>\n\n"
        f"Статус: {'включен' if config.get('enabled') else 'выключен'}\n"
        f"Разрешённые количества: {', '.join(map(str, get_allowed_quantities())) or '-'}\n"
        f"Fragment hash: {'задан' if fragment.get('hash') else 'не задан'}\n"
        f"Fragment cookie: {'задан' if fragment.get('cookie') else 'не задан'}\n"
        f"TON API key: {'задан' if ton.get('api_key') else 'не задан'}\n"
        f"TON destination: {'задан' if ton.get('destination_address') else 'не задан'}\n"
        f"Мнемоника: {'задана' if len(ton.get('mnemonic') or []) == 24 else 'не задана'}\n"
        f"Автовозврат: {'включён' if config.get('auto_refund') else 'выключен'}\n\n"
        f"За сегодня:\n"
        f"Успешно: {success}\n"
        f"Неуспешно: {failed}"
    )


def menu_kb() -> InlineKeyboardMarkup:
    enabled = bool(get_config().get("enabled"))
    rows = [
        [InlineKeyboardButton(text=("Выключить" if enabled else "Включить"), callback_data="as_toggle_enabled")],
        [InlineKeyboardButton(text="Сообщения", callback_data="as_messages_menu")],
        [InlineKeyboardButton(text="Настройки", callback_data="as_settings_menu")],
        [InlineKeyboardButton(text="Назад", callback_data="destroy")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def messages_text() -> str:
    messages = get_messages()
    return (
        "<b>Сообщения AutoStars</b>\n\n"
        f"new_order:\n<blockquote>{messages.get('new_order', '')}</blockquote>\n\n"
        f"confirm_username:\n<blockquote>{messages.get('confirm_username', '')}</blockquote>\n\n"
        f"queue_added:\n<blockquote>{messages.get('queue_added', '')}</blockquote>\n\n"
        f"completed:\n<blockquote>{messages.get('completed', '')}</blockquote>\n\n"
        f"payment_failed:\n<blockquote>{messages.get('payment_failed', '')}</blockquote>"
    )


def messages_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="new_order", callback_data="as_message:new_order")],
        [InlineKeyboardButton(text="confirm_username", callback_data="as_message:confirm_username")],
        [InlineKeyboardButton(text="queue_added", callback_data="as_message:queue_added")],
        [InlineKeyboardButton(text="completed", callback_data="as_message:completed")],
        [InlineKeyboardButton(text="payment_failed", callback_data="as_message:payment_failed")],
        [InlineKeyboardButton(text="Назад", callback_data="as_back")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def settings_text() -> str:
    return "<b>Настройки AutoStars</b>\n\nВыберите параметр, который хотите изменить."


def settings_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="Fragment hash", callback_data="as_setting:fragment_hash")],
        [InlineKeyboardButton(text="Fragment cookie", callback_data="as_setting:fragment_cookie")],
        [InlineKeyboardButton(text="TON API key", callback_data="as_setting:ton_api_key")],
        [InlineKeyboardButton(text="TON destination", callback_data="as_setting:ton_destination")],
        [InlineKeyboardButton(text="TON mnemonic", callback_data="as_setting:ton_mnemonic")],
        [InlineKeyboardButton(text="Allowed quantities", callback_data="as_setting:allowed_quantities")],
        [InlineKeyboardButton(text="Автовозврат", callback_data="as_toggle_refund")],
        [InlineKeyboardButton(text="Назад", callback_data="as_back")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def edit_message_prompt(message_key: str) -> str:
    return f"Отправьте новый текст для <code>{message_key}</code>."


def edit_setting_prompt(setting_key: str) -> str:
    prompts = {
        "fragment_hash": "Отправьте новый Fragment hash.",
        "fragment_cookie": "Отправьте новый Fragment cookie.",
        "ton_api_key": "Отправьте новый TON API key.",
        "ton_destination": "Отправьте новый TON destination address.",
        "ton_mnemonic": "Отправьте 24 слова мнемоники через пробел.",
        "allowed_quantities": "Отправьте количества через запятую. Пример: 10,50,100,250",
    }
    return prompts.get(setting_key, "Отправьте новое значение.")
