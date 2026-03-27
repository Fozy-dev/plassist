from __future__ import annotations

import math
import textwrap

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from .meta import NAME, PRICE
from .storage import get_bonuses, get_config, get_messages


def _status_label() -> str:
    return "🟢 Включен" if bool(get_config().get("enabled")) else "🔴 Выключен"


def _bonus_preview(text: str, limit: int = 46) -> str:
    compact = " ".join((text or "").split())
    return compact if len(compact) <= limit else compact[: limit - 1] + "…"


def menu_text() -> str:
    config = get_config()
    bonuses_count = len(config.get("bonuses") or [])
    enabled = _status_label()
    return textwrap.dedent(
        f"""
        ⚡ <b>{NAME}</b>

        <b>Статус:</b> {enabled}
        <b>Бонусов:</b> {bonuses_count}

        Автоматически выдавай бонусы покупателям после
        подтверждения сделки или оставления отзыва.

        Работает на Playerok и FunPay.
        """
    ).strip()


def menu_kb() -> InlineKeyboardMarkup:
    enabled = bool(get_config().get("enabled"))
    rows = [
        [InlineKeyboardButton(text=("🔴 Выключить" if enabled else "🟢 Включить"), callback_data="ab_toggle_enabled")],
        [InlineKeyboardButton(text="💬 Сообщения", callback_data="ab_messages_menu")],
        [InlineKeyboardButton(text="🎁 Бонусы", callback_data="ab_bonuses_menu")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="destroy")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def messages_text() -> str:
    messages = get_messages()
    return textwrap.dedent(
        f"""
        💬 <b>{NAME}</b> — сообщения

        <b>При новой сделке:</b>
        <blockquote>{messages.get('new_deal', '')}</blockquote>

        <b>Сообщение с бонусом:</b>
        <blockquote>{messages.get('bonus_sent', '')}</blockquote>

        <b>Если бонус не найден:</b>
        <blockquote>{messages.get('bonus_not_found', '')}</blockquote>
        """
    ).strip()


def messages_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="✉️ Новая сделка", callback_data="ab_message:new_deal")],
        [InlineKeyboardButton(text="🎁 Сообщение с бонусом", callback_data="ab_message:bonus_sent")],
        [InlineKeyboardButton(text="❌ Бонус не найден", callback_data="ab_message:bonus_not_found")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="ab_back")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def message_page_text(message_key: str) -> str:
    messages = get_messages()
    title_map = {
        "new_deal": "Сообщение при новой сделке",
        "bonus_sent": "Сообщение с бонусом",
        "bonus_not_found": "Сообщение если бонус не найден",
    }
    return textwrap.dedent(
        f"""
        ✏️ <b>{title_map.get(message_key, message_key)}</b>

        <blockquote>{messages.get(message_key, '')}</blockquote>

        Отправьте новый текст одним сообщением.
        """
    ).strip()


def message_page_kb(message_key: str) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="ab_messages_menu")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def bonuses_text(page: int = 0) -> str:
    bonuses = get_bonuses()
    total = len(bonuses)
    pages = math.ceil(total / 6) if total else 1
    return textwrap.dedent(
        f"""
        🎁 <b>{NAME}</b> — бонусы

        Всего привязок: <b>{total}</b>
        Страница: <b>{page + 1}/{pages}</b>

        Нажмите на бонус, чтобы открыть его редактирование.
        """
    ).strip()


def bonuses_kb(page: int = 0) -> InlineKeyboardMarkup:
    bonuses = get_bonuses()
    rows = []
    items_per_page = 6
    total_pages = math.ceil(len(bonuses) / items_per_page) if bonuses else 1
    page = max(0, min(page, total_pages - 1))
    start = page * items_per_page
    end = start + items_per_page
    for bonus in bonuses[start:end]:
        text = f"{bonus.get('target') or '-'} — {_bonus_preview(bonus.get('bonus') or '-')}"
        rows.append([InlineKeyboardButton(text=text, callback_data=f"ab_bonus:{bonus['id']}")])

    nav_row = [
        InlineKeyboardButton(text="←", callback_data=f"ab_bonuses_page:{page - 1}" if page > 0 else "ab_void"),
        InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="ab_void"),
        InlineKeyboardButton(text="→", callback_data=f"ab_bonuses_page:{page + 1}" if page < total_pages - 1 else "ab_void"),
    ]
    rows.append(nav_row)
    rows.append([InlineKeyboardButton(text="➕ Привязать бонус", callback_data="ab_add_bonus")])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="ab_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def bonus_page_text(bonus: dict) -> str:
    return textwrap.dedent(
        f"""
        🎁 <b>Бонус</b>

        <b>Товар:</b> <blockquote>{bonus.get('target') or '-'}</blockquote>
        <b>Текст бонуса:</b> <blockquote>{bonus.get('bonus') or '-'}</blockquote>
        """
    ).strip()


def bonus_page_kb(bonus_id: str) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="✏️ Изменить товар", callback_data=f"ab_edit_target:{bonus_id}")],
        [InlineKeyboardButton(text="✏️ Изменить бонус", callback_data=f"ab_edit_bonus:{bonus_id}")],
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"ab_delete_bonus:{bonus_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="ab_bonuses_menu")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def prompt_text(message: str) -> str:
    return textwrap.dedent(
        f"""
        ⚡ <b>{NAME}</b>

        {message}
        """
    ).strip()
