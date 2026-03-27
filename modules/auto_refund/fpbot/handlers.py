from __future__ import annotations

from FunPayAPI.types import MessageTypes
from FunPayAPI.updater.events import EventTypes

from tgbot.telegrambot import get_telegram_bot, get_telegram_bot_loop

from ..helpers import format_message, parse_order_id
from ..storage import (
    get_max_price,
    get_messages,
    get_ratings,
    is_enabled,
    is_notify_buyer_enabled,
    is_owned,
    mark_refunded,
    was_refunded,
)

import asyncio


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


async def on_new_message(bot, event):
    if not is_enabled() or not is_owned():
        return
    if event.message.author == bot.account.username:
        return
    if event.message.type not in {MessageTypes.NEW_FEEDBACK, MessageTypes.FEEDBACK_CHANGED}:
        return

    order_id = parse_order_id(event.message.text)
    if not order_id or was_refunded(order_id):
        return

    try:
        order = bot.account.get_order(order_id)
    except Exception:
        return

    review = getattr(order, "review", None)
    if not review:
        return

    stars = int(getattr(review, "stars", 0) or 0)
    if stars < 1 or stars > 5:
        return
    if not get_ratings().get(str(stars), False):
        return

    try:
        price = float(getattr(order, "price", None) or getattr(order, "sum", None) or 0)
    except Exception:
        price = 0.0

    max_price = get_max_price()
    if max_price > 0 and price > max_price:
        return

    try:
        bot.account.refund(order_id)
    except Exception as exc:
        await _notify_admins(
            format_message(
                get_messages().get("refund_failed", ""),
                order_id=order_id,
                error=str(exc),
            )
        )
        return

    mark_refunded(order_id, stars, price, getattr(review, "author", "?"))

    if is_notify_buyer_enabled():
        try:
            bot.send_message(
                event.message.chat_id,
                format_message(
                    get_messages().get("refund_sent", ""),
                    order_id=order_id,
                    stars=stars,
                    price=price,
                ),
            )
        except Exception:
            pass

    await _notify_admins(
        format_message(
            get_messages().get("admin_log", ""),
            order_id=order_id,
            stars=stars,
            price=price,
            author=getattr(review, "author", "?"),
        )
    )


FUNPAY_EVENT_HANDLERS = {
    EventTypes.NEW_MESSAGE: [on_new_message],
}
