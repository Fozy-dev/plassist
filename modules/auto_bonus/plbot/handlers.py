from __future__ import annotations

from playerokapi.enums import ItemDealStatuses
from playerokapi.listener.events import EventTypes

from ..helpers import format_message, match_bonus, normalize
from ..storage import get_bonuses, get_messages, is_enabled, is_owned, set_sent_deal, was_sent


def _deal_key(deal_id: int | str) -> str:
    return f"playerok:{deal_id}"


def _send_new_deal(bot, event):
    if not is_enabled() or not is_owned():
        return
    messages = get_messages()
    bot.send_message(
        event.chat.id,
        messages.get("new_deal", ""),
    )


async def on_new_deal(bot, event):
    if event.deal.user.id == bot.account.id:
        return
    _send_new_deal(bot, event)


async def on_deal_status_changed(bot, event):
    if event.deal.user.id == bot.account.id or not is_enabled() or not is_owned():
        return
    status_name = getattr(event.deal.status, "name", str(event.deal.status))
    if status_name not in {"CONFIRMED", "CONFIRMED_AUTOMATICALLY"}:
        return
    deal_key = _deal_key(event.deal.id)
    if was_sent(deal_key):
        return

    item = getattr(event.deal, "item", None)
    bonus = match_bonus(get_bonuses(), getattr(item, "id", None), getattr(item, "name", None))
    if bonus:
        bot.send_message(
            event.chat.id,
            format_message(get_messages().get("bonus_sent", ""), bonus=bonus.get("bonus", ""), item_name=getattr(item, "name", ""), deal_id=event.deal.id),
        )
    else:
        bot.send_message(
            event.chat.id,
            get_messages().get("bonus_not_found", ""),
        )
    set_sent_deal(deal_key)


async def on_deal_confirmed(bot, event):
    await on_deal_status_changed(bot, event)


async def on_deal_confirmed_auto(bot, event):
    await on_deal_status_changed(bot, event)


BOT_EVENT_HANDLERS = {}
PLAYEROK_EVENT_HANDLERS = {
    EventTypes.NEW_DEAL: [on_new_deal],
    EventTypes.DEAL_STATUS_CHANGED: [on_deal_status_changed],
    EventTypes.DEAL_CONFIRMED: [on_deal_confirmed],
    EventTypes.DEAL_CONFIRMED_AUTOMATICALLY: [on_deal_confirmed_auto],
}
