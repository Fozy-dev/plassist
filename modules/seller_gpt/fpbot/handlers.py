from __future__ import annotations

import asyncio

import requests
from FunPayAPI.types import MessageTypes
from FunPayAPI.updater.events import EventTypes

from tgbot.telegrambot import get_telegram_bot

from ..helpers import contains_url, format_message, parse_lot_id
from ..storage import (
    get_api_base_url,
    get_api_key,
    get_history_limit,
    get_messages,
    get_model,
    get_prompt,
    get_timeout_sec,
    is_enabled,
    is_ignore_links,
    is_owned,
    is_use_lot_context,
    mark_handled,
    was_handled,
)


async def _notify_admins(text: str):
    telegram = get_telegram_bot()
    if not telegram:
        return
    signed_users = ((telegram.config or {}).get("telegram", {}).get("bot", {}).get("signed_users", []) or [])
    for user_id in signed_users:
        try:
            await telegram.bot.send_message(chat_id=user_id, text=text)
        except Exception:
            continue


def _generate_reply(messages: list[dict]) -> str:
    api_key = get_api_key()
    api_base_url = get_api_base_url().rstrip("/")
    model = get_model()
    if not api_key or not api_base_url or not model:
        raise RuntimeError("Не заполнены api_key / api_base_url / model")

    response = requests.post(
        f"{api_base_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": messages,
            "temperature": 0.8,
        },
        timeout=get_timeout_sec(),
    )
    response.raise_for_status()
    payload = response.json()
    choices = payload.get("choices") or []
    if not choices:
        raise RuntimeError("API не вернул choices")
    message = (choices[0] or {}).get("message") or {}
    content = str(message.get("content", "") or "").strip()
    if not content:
        raise RuntimeError("API вернул пустой ответ")
    return content


def _build_messages(bot, chat, author_name: str) -> list[dict]:
    messages: list[dict] = [
        {"role": "system", "content": get_prompt()},
        {"role": "system", "content": f"Собеседник: {author_name}. Чат: {chat.id}."},
    ]

    if is_use_lot_context() and getattr(chat, "looking_link", None):
        lot_id = parse_lot_id(chat.looking_link)
        if lot_id:
            try:
                lot_fields = bot.account.get_lot_fields(lot_id)
                lot_title = getattr(lot_fields, "title_ru", None) or getattr(lot_fields, "title_en", None) or getattr(chat, "looking_text", None) or ""
                lot_description = getattr(lot_fields, "description_ru", None) or getattr(lot_fields, "description_en", None) or ""
                lot_price = getattr(lot_fields, "price", None) or ""
                if lot_title or lot_description or lot_price:
                    messages.append(
                        {
                            "role": "system",
                            "content": (
                                f"Покупатель сейчас смотрит лот. Название: {lot_title}. "
                                f"Цена: {lot_price}. Описание: {lot_description}"
                            ).strip(),
                        }
                    )
            except Exception:
                pass

    history = [m for m in getattr(chat, "messages", []) if getattr(m, "text", None)]
    history = history[-get_history_limit():]
    for item in history:
        role = "assistant" if getattr(item, "author_id", None) == bot.account.id else "user"
        messages.append({"role": role, "content": str(item.text).strip()})
    return messages


async def on_new_message(bot, event):
    if not is_enabled() or not is_owned():
        return
    if event.message.author == bot.account.username or event.message.author_id == bot.account.id:
        return
    if event.message.type is not MessageTypes.NON_SYSTEM:
        return
    if not event.message.text or not str(event.message.text).strip():
        return
    if was_handled(event.message.id):
        return

    text = str(event.message.text).strip()
    if text.startswith(("/", "!")):
        return
    if is_ignore_links() and contains_url(text):
        return

    try:
        chat = bot.account.get_chat(event.message.chat_id, with_history=True)
        messages = _build_messages(bot, chat, event.message.author or chat.name or "покупатель")
        reply_text = await asyncio.to_thread(_generate_reply, messages)
        bot.send_message(event.message.chat_id, reply_text)
    except Exception as exc:
        await _notify_admins(
            format_message(
                get_messages().get("reply_failed", ""),
                chat_id=event.message.chat_id,
                author=event.message.author or "?",
                error=str(exc),
            )
        )
        return

    mark_handled(event.message.id)
    await _notify_admins(
        format_message(
            get_messages().get("admin_log", ""),
            chat_id=event.message.chat_id,
            author=event.message.author or "?",
        )
    )


FUNPAY_EVENT_HANDLERS = {
    EventTypes.NEW_MESSAGE: [on_new_message],
}
