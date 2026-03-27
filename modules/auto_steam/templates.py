from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .helpers import bool_text, mask_secret
from .storage import (
    get_allowed_subcategory_ids,
    get_api_login,
    get_api_password,
    get_blacklist_logins,
    get_history,
    get_messages,
    get_reminder_time_minutes,
    is_auto_refund_enabled,
    is_confirmation_reminder_enabled,
    is_enabled,
    is_order_verification_enabled,
)


def menu_text(balance: str = "?") -> str:
    return (
        "<b>AutoSteam</b>\n\n"
        f"Статус: <b>{bool_text(is_enabled())}</b>\n"
        f"API login: <code>{get_api_login() or 'не задан'}</code>\n"
        f"API password: <code>{mask_secret(get_api_password())}</code>\n"
        f"Баланс NSGifts: <code>{balance}</code>\n"
        f"Автовозврат: <b>{bool_text(is_auto_refund_enabled())}</b>\n"
        f"Проверка заказа: <b>{bool_text(is_order_verification_enabled())}</b>\n"
        f"Напоминание: <b>{bool_text(is_confirmation_reminder_enabled())}</b> ({get_reminder_time_minutes()} мин.)\n"
        f"Подкатегории: <code>{', '.join(map(str, get_allowed_subcategory_ids()))}</code>\n"
        f"Steam blacklist: <code>{len(get_blacklist_logins())}</code>\n"
        f"История: <code>{len(get_history())}</code>"
    )


def menu_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Переключить", callback_data="ast_toggle_enabled")
    kb.button(text="API login", callback_data="ast_edit_api_login")
    kb.button(text="API password", callback_data="ast_edit_api_password")
    kb.button(text="Автовозврат", callback_data="ast_toggle_auto_refund")
    kb.button(text="Проверка заказа", callback_data="ast_toggle_verification")
    kb.button(text="Напоминание", callback_data="ast_toggle_reminder")
    kb.button(text="Время напоминания", callback_data="ast_edit_reminder_time")
    kb.button(text="Подкатегории", callback_data="ast_edit_subcategories")
    kb.button(text="Steam blacklist", callback_data="ast_blacklist_menu")
    kb.button(text="История", callback_data="ast_history_menu")
    kb.button(text="Сообщения", callback_data="ast_messages_menu")
    kb.adjust(1, 2, 2, 2, 2, 1)
    return kb.as_markup()


def messages_text() -> str:
    messages = get_messages()
    keys = ["ask_login", "confirm_login", "queue_added", "success", "invalid_login", "refund", "reply_plus", "admin_log", "admin_error", "reminder"]
    return "<b>AutoSteam • Сообщения</b>\n\n" + "\n\n".join([f"{key}:\n<code>{messages.get(key, '')}</code>" for key in keys])


def messages_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for key in ["ask_login", "confirm_login", "queue_added", "success", "invalid_login", "refund", "reply_plus", "admin_log", "admin_error", "reminder"]:
        kb.button(text=key, callback_data=f"ast_message:{key}")
    kb.button(text="Назад", callback_data="ast_back")
    kb.adjust(1)
    return kb.as_markup()


def edit_message_prompt(message_key: str) -> str:
    return f"<b>AutoSteam</b>\n\nОтправьте новый текст для <code>{message_key}</code>."


def blacklist_text() -> str:
    values = get_blacklist_logins()
    lines = ["<b>AutoSteam • Blacklist</b>", ""]
    lines.extend([f"- <code>{value}</code>" for value in values] or ["Список пуст."])
    return "\n".join(lines)


def blacklist_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Добавить", callback_data="ast_blacklist_add")
    kb.button(text="Удалить", callback_data="ast_blacklist_remove")
    kb.button(text="Назад", callback_data="ast_back")
    kb.adjust(2, 1)
    return kb.as_markup()


def history_text(limit: int = 15) -> str:
    history = list(reversed(get_history()))[:limit]
    lines = ["<b>AutoSteam • История</b>", ""]
    if not history:
        lines.append("История пуста.")
    else:
        for item in history:
            lines.append(f"#{item.get('order_id')} | {item.get('steam_login')} | {item.get('quantity')} {item.get('currency')} | {item.get('status')}")
    return "\n".join(lines)


def history_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Назад", callback_data="ast_back")
    return kb.as_markup()
