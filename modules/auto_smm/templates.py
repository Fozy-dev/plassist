from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .helpers import bool_text, mask_secret
from .storage import (
    get_allowed_domains,
    get_api_key,
    get_api_url,
    get_history,
    get_mappings,
    get_messages,
    is_auto_refund_enabled,
    is_confirm_link_enabled,
    is_enabled,
)


MESSAGE_KEYS = [
    "after_payment",
    "confirm_link",
    "queue_added",
    "after_confirmation",
    "invalid_link",
    "mapping_not_found",
    "reply_plus",
    "refund",
    "admin_log",
    "admin_error",
]


def menu_text(balance: str = "?") -> str:
    return (
        "<b>AutoSMM</b>\n\n"
        f"Статус: <b>{bool_text(is_enabled())}</b>\n"
        f"API URL: <code>{get_api_url() or 'не задан'}</code>\n"
        f"API KEY: <code>{mask_secret(get_api_key())}</code>\n"
        f"Баланс API: <code>{balance}</code>\n"
        f"Автовозврат: <b>{bool_text(is_auto_refund_enabled())}</b>\n"
        f"Подтверждение ссылки: <b>{bool_text(is_confirm_link_enabled())}</b>\n"
        f"Домены: <code>{len(get_allowed_domains())}</code>\n"
        f"Маппинги: <code>{len(get_mappings())}</code>\n"
        f"История: <code>{len(get_history())}</code>"
    )


def menu_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Переключить", callback_data="asm_toggle_enabled")
    kb.button(text="API URL", callback_data="asm_edit_api_url")
    kb.button(text="API KEY", callback_data="asm_edit_api_key")
    kb.button(text="Автовозврат", callback_data="asm_toggle_auto_refund")
    kb.button(text="Подтв. ссылки", callback_data="asm_toggle_confirm_link")
    kb.button(text="Домены", callback_data="asm_domains_menu")
    kb.button(text="Маппинги", callback_data="asm_mappings_menu")
    kb.button(text="Сообщения", callback_data="asm_messages_menu")
    kb.button(text="История", callback_data="asm_history_menu")
    kb.adjust(1, 2, 2, 2, 1, 1)
    return kb.as_markup()


def messages_text() -> str:
    messages = get_messages()
    return "<b>AutoSMM • Сообщения</b>\n\n" + "\n\n".join([f"{key}:\n<code>{messages.get(key, '')}</code>" for key in MESSAGE_KEYS])


def messages_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for key in MESSAGE_KEYS:
        kb.button(text=key, callback_data=f"asm_message:{key}")
    kb.button(text="Назад", callback_data="asm_back")
    kb.adjust(1)
    return kb.as_markup()


def edit_message_prompt(message_key: str) -> str:
    return f"<b>AutoSMM</b>\n\nОтправьте новый текст для <code>{message_key}</code>."


def domains_text() -> str:
    values = get_allowed_domains()
    lines = ["<b>AutoSMM • Разрешённые домены</b>", ""]
    lines.extend([f"- <code>{value}</code>" for value in values] or ["Список пуст."])
    return "\n".join(lines)


def domains_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Добавить", callback_data="asm_domain_add")
    kb.button(text="Удалить", callback_data="asm_domain_remove")
    kb.button(text="Назад", callback_data="asm_back")
    kb.adjust(2, 1)
    return kb.as_markup()


def mappings_text() -> str:
    mappings = get_mappings()
    lines = ["<b>AutoSMM • Маппинги</b>", ""]
    if not mappings:
        lines.append("Маппинги не настроены.")
    else:
        for idx, item in enumerate(mappings, start=1):
            lines.append(
                f"{idx}. <b>{item.get('name') or 'Без имени'}</b>\n"
                f"Фраза: <code>{item.get('phrase')}</code>\n"
                f"service_id: <code>{item.get('service_id')}</code>\n"
                f"quantity: <code>{item.get('quantity')}</code>\n"
            )
    return "\n".join(lines)


def mappings_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Добавить", callback_data="asm_mapping_add")
    kb.button(text="Удалить", callback_data="asm_mapping_remove")
    kb.button(text="Назад", callback_data="asm_back")
    kb.adjust(2, 1)
    return kb.as_markup()


def history_text(limit: int = 15) -> str:
    history = list(reversed(get_history()))[:limit]
    lines = ["<b>AutoSMM • История</b>", ""]
    if not history:
        lines.append("История пуста.")
    else:
        for item in history:
            lines.append(f"#{item.get('order_id')} | {item.get('link')} | {item.get('status')}")
    return "\n".join(lines)


def history_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Назад", callback_data="asm_back")
    return kb.as_markup()
