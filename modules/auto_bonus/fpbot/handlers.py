from __future__ import annotations

from FunPayAPI.common.enums import OrderStatuses
from FunPayAPI.updater.events import EventTypes, MessageTypes

from ..helpers import format_message, match_bonus
from ..storage import get_bonuses, get_messages, is_enabled, is_owned, set_sent_deal, was_sent


def _order_key(order_id: int | str) -> str:
    return f"funpay:{order_id}"


async def on_new_order(bot, event):
    if event.order.buyer_username == bot.account.username or not is_enabled() or not is_owned():
        return
    chat = bot.account.get_chat_by_name(event.order.buyer_username, True)
    if not chat:
        return
    bot.send_message(chat.id, get_messages().get("new_deal", ""))


async def on_new_message(bot, event):
    if not is_enabled() or not is_owned():
        return
    if event.message.type is not MessageTypes.NEW_FEEDBACK:
        return
    if event.message.author == bot.account.username:
        return

    try:
        order_id = event.message.text.split(" ")[-1].replace("#", "").replace(".", "")
    except Exception:
        return

    order = bot.account.get_order(order_id)
    if not order:
        return

    order_key = _order_key(order.id)
    if was_sent(order_key):
        return

    lot = bot.get_lot_by_order_title(order.description, getattr(order, "subcategory", None))
    target_id = getattr(lot, "id", None)
    bonus = match_bonus(get_bonuses(), target_id, order.description)
    chat = bot.account.get_chat_by_name(order.buyer_username, True)
    if not chat:
        return

    if bonus:
        bot.send_message(
            chat.id,
            format_message(get_messages().get("bonus_sent", ""), bonus=bonus.get("bonus", ""), item_name=order.description, deal_id=order.id),
        )
    else:
        bot.send_message(chat.id, get_messages().get("bonus_not_found", ""))
    set_sent_deal(order_key)


BOT_EVENT_HANDLERS = {}
PLAYEROK_EVENT_HANDLERS = {}
FUNPAY_EVENT_HANDLERS = {
    EventTypes.NEW_ORDER: [on_new_order],
    EventTypes.NEW_MESSAGE: [on_new_message],
}
