from __future__ import annotations

from datetime import datetime

from FunPayAPI.updater.events import EventTypes

from ..helpers import format_message, is_valid_username, normalize_username, parse_stars_quantity
from ..services import service
from ..storage import (
    add_pending_order,
    get_last_pending_order,
    get_messages,
    is_enabled,
    is_owned,
    mark_completed,
    update_pending_order,
)


async def on_new_order(bot, event):
    if not is_enabled() or not is_owned():
        return
    if event.order.buyer_username == bot.account.username:
        return
    quantity = parse_stars_quantity(getattr(event.order, "description", ""))
    if not quantity:
        return
    total_stars = quantity * max(int(getattr(event.order, "amount", 1) or 1), 1)
    chat = bot.account.get_chat_by_name(event.order.buyer_username, True)
    if not chat:
        return
    add_pending_order(
        chat.id,
        {
            "order_id": str(event.order.id),
            "buyer_username": event.order.buyer_username,
            "quantity": total_stars,
            "status": "waiting_username",
            "confirmed": False,
            "completed": False,
            "cancelled": False,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        },
    )
    bot.send_message(chat.id, format_message(get_messages().get("new_order", ""), quantity=total_stars))


async def on_new_message(bot, event):
    if not is_enabled() or not is_owned():
        return
    if event.message.author.lower() in {"funpay", bot.account.username.lower()}:
        return
    pending = get_last_pending_order(event.message.chat_id)
    if not pending:
        return

    text = (event.message.text or "").strip()
    messages = get_messages()

    if text.lower() == "!бек":
        try:
            bot.account.refund(pending["order_id"])
        except Exception:
            pass
        mark_completed(event.message.chat_id, pending["order_id"], completed=False, cancelled=True)
        bot.send_message(event.message.chat_id, messages.get("cancelled", "Заказ отменён, средства возвращены."))
        return

    if pending.get("status") == "waiting_username":
        if not is_valid_username(text):
            bot.send_message(event.message.chat_id, messages.get("invalid_username", "Неверный формат username."))
            return
        username = normalize_username(text)
        preview = await service.search_recipient_preview(username)
        update_pending_order(
            event.message.chat_id,
            pending["order_id"],
            username=username,
            status="waiting_confirm",
            preview_name=preview.get("preview_name"),
            recipient_id=preview.get("recipient_id"),
        )
        bot.send_message(
            event.message.chat_id,
            format_message(
                messages.get("confirm_username", ""),
                username=username,
                preview_name=preview.get("preview_name"),
                recipient_id=preview.get("recipient_id"),
            ),
        )
        return

    if pending.get("status") == "waiting_confirm":
        lowered = text.lower()
        if lowered == "нет":
            update_pending_order(
                event.message.chat_id,
                pending["order_id"],
                username=None,
                status="waiting_username",
                confirmed=False,
            )
            bot.send_message(event.message.chat_id, messages.get("ask_username_again", "Отправьте @username ещё раз."))
            return
        if lowered != "да":
            bot.send_message(event.message.chat_id, messages.get("reply_yes_no", "Ответьте Да или Нет."))
            return
        position = service.enqueue(
            bot,
            event.message.chat_id,
            pending.get("username") or "",
            int(pending.get("quantity") or 0),
            str(pending.get("order_id") or ""),
        )
        update_pending_order(
            event.message.chat_id,
            pending["order_id"],
            status="processing",
            confirmed=True,
        )
        bot.send_message(
            event.message.chat_id,
            format_message(messages.get("queue_added", ""), position=position),
        )


FUNPAY_EVENT_HANDLERS = {
    EventTypes.NEW_ORDER: [on_new_order],
    EventTypes.NEW_MESSAGE: [on_new_message],
}
