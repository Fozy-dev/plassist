from __future__ import annotations

from FunPayAPI.common.enums import MessageTypes, OrderStatuses
from FunPayAPI.updater.events import EventTypes

from ..helpers import extract_first_url, extract_order_id_from_message, find_mapping, format_message, is_allowed_url
from ..services import service
from ..storage import get_allowed_domains, get_mappings, get_messages, is_confirm_link_enabled, is_enabled, is_owned


def _order_text(order) -> str:
    parts = [
        getattr(order, "html", "") or "",
        getattr(order, "description", "") or "",
        getattr(order, "short_description", "") or "",
        getattr(order, "subcategory", None).name if getattr(order, "subcategory", None) else "",
    ]
    return "\n".join([str(i) for i in parts if i])


async def on_new_order(bot, event):
    if not is_enabled() or not is_owned():
        return
    if getattr(event.order, "buyer_username", None) == bot.account.username:
        return
    order_text = _order_text(event.order)
    mapping = find_mapping(order_text, get_mappings())
    chat = bot.account.get_chat_by_name(event.order.buyer_username, True)
    if not chat:
        return
    if not mapping:
        bot.send_message(chat.id, get_messages().get("mapping_not_found", "Для этого лота нет маппинга."))
        return
    service.set_state(
        chat.id,
        int(getattr(event.order, "buyer_id", 0) or 0),
        {"state": "waiting_for_link", "data": {"order_id": str(event.order.id), "mapping": mapping}},
    )
    bot.send_message(chat.id, format_message(get_messages().get("after_payment", ""), order_id=event.order.id))


async def on_new_message(bot, event):
    if not is_enabled() or not is_owned():
        return
    if event.message.author_id == bot.account.id or event.message.author == bot.account.username:
        return

    if event.message.author_id == 0 and event.message.type and getattr(event.message.type, "name", "") == "ORDER_PURCHASED":
        order_id = extract_order_id_from_message(event.message.text)
        if order_id:
            try:
                order = bot.account.get_order(order_id)
                fake_event = type("E", (), {"order": order})
                return await on_new_order(bot, fake_event)
            except Exception:
                return

    state = service.get_state(event.message.chat_id, event.message.author_id)
    if not state or event.message.type is not MessageTypes.NON_SYSTEM:
        return

    text = (event.message.text or "").strip()
    data = dict(state.get("data") or {})
    order_id = str(data.get("order_id") or "")
    mapping = dict(data.get("mapping") or {})

    try:
        order = bot.account.get_order(order_id)
        if getattr(order, "status", None) in {OrderStatuses.CLOSED, OrderStatuses.REFUNDED}:
            service.set_state(event.message.chat_id, event.message.author_id, None)
            return
    except Exception:
        pass

    if state.get("state") == "waiting_for_link":
        link = extract_first_url(text)
        if not link or not is_allowed_url(link, get_allowed_domains()):
            bot.send_message(event.message.chat_id, get_messages().get("invalid_link", "Ссылка не подходит."))
            return
        if is_confirm_link_enabled():
            service.set_state(event.message.chat_id, event.message.author_id, {"state": "confirming_link", "data": {**data, "link": link}})
            bot.send_message(event.message.chat_id, format_message(get_messages().get("confirm_link", ""), link=link))
            return
        position = service.enqueue(bot, order_id, event.message.chat_id, int(event.message.author_id), link, int(mapping.get("service_id", 0)), int(mapping.get("quantity", 0)))
        service.set_state(event.message.chat_id, event.message.author_id, {"state": "processing", "data": {**data, "link": link}})
        bot.send_message(event.message.chat_id, format_message(get_messages().get("queue_added", ""), position=position))
        return

    if state.get("state") == "confirming_link":
        if text == "+":
            link = str(data.get("link") or "")
            position = service.enqueue(bot, order_id, event.message.chat_id, int(event.message.author_id), link, int(mapping.get("service_id", 0)), int(mapping.get("quantity", 0)))
            service.set_state(event.message.chat_id, event.message.author_id, {"state": "processing", "data": data})
            bot.send_message(event.message.chat_id, format_message(get_messages().get("queue_added", ""), position=position))
            return
        new_link = extract_first_url(text)
        if new_link and is_allowed_url(new_link, get_allowed_domains()):
            service.set_state(event.message.chat_id, event.message.author_id, {"state": "confirming_link", "data": {**data, "link": new_link}})
            bot.send_message(event.message.chat_id, format_message(get_messages().get("confirm_link", ""), link=new_link))
            return
        bot.send_message(event.message.chat_id, get_messages().get("reply_plus", "Отправьте + или новую ссылку."))


FUNPAY_EVENT_HANDLERS = {EventTypes.NEW_ORDER: [on_new_order], EventTypes.NEW_MESSAGE: [on_new_message]}
