from __future__ import annotations

import asyncio

import requests
from FunPayAPI.types import MessageTypes
from FunPayAPI.updater.events import EventTypes

from tgbot.telegrambot import get_telegram_bot

from ..helpers import build_prompt, format_message, parse_order_id
from ..storage import (
    get_api_base_url,
    get_api_key,
    get_messages,
    get_min_stars,
    get_model,
    get_prompt,
    get_timeout_sec,
    is_enabled,
    is_only_without_reply,
    is_owned,
    mark_replied,
    was_replied,
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


def _generate_reply(prompt: str) -> str:
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
            "messages": [
                {"role": "system", "content": "Ты пишешь ответы продавца на отзывы покупателей."},
                {"role": "user", "content": prompt},
            ],
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


async def on_new_message(bot, event):
    if not is_enabled() or not is_owned():
        return
    if event.message.author == bot.account.username:
        return
    if event.message.type not in {MessageTypes.NEW_FEEDBACK, MessageTypes.FEEDBACK_CHANGED}:
        return

    order_id = parse_order_id(event.message.text)
    if not order_id or was_replied(order_id):
        return

    try:
        order = bot.account.get_order(order_id)
    except Exception:
        return

    review = getattr(order, "review", None)
    if not review:
        return

    stars = int(getattr(review, "stars", 0) or 0)
    if stars < get_min_stars():
        return

    if is_only_without_reply() and getattr(review, "reply", None):
        return

    prompt = build_prompt(get_prompt(), order, review)

    try:
        reply_text = await asyncio.to_thread(_generate_reply, prompt)
        bot.account.send_review(order_id, reply_text, rating=max(1, min(5, stars or 5)))
    except Exception as exc:
        await _notify_admins(
            format_message(
                get_messages().get("reply_failed", ""),
                order_id=order_id,
                error=str(exc),
            )
        )
        return

    mark_replied(order_id)
    await _notify_admins(
        format_message(
            get_messages().get("admin_log", ""),
            order_id=order_id,
            stars=stars,
            author=getattr(review, "author", "?"),
        )
    )


FUNPAY_EVENT_HANDLERS = {
    EventTypes.NEW_MESSAGE: [on_new_message],
}
