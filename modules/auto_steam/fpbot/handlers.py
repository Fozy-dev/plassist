from __future__ import annotations

from FunPayAPI.common.enums import MessageTypes, OrderStatuses
from FunPayAPI.updater.events import EventTypes

from ..helpers import extract_currency, extract_order_id_from_message, extract_quantity, extract_steam_login, format_message, is_valid_steam_login
from ..services import service
from ..storage import get_allowed_subcategory_ids, get_blacklist_logins, get_messages, is_enabled, is_order_verification_enabled, is_owned


def _verify_order(bot, order_id: str) -> bool:
    try:
        order = bot.account.get_order(order_id)
        return getattr(order, 'seller_id', None) == bot.account.id
    except Exception:
        return False


async def on_new_order(bot, event):
    if not is_enabled() or not is_owned():
        return
    if getattr(event.order, 'buyer_username', None) == bot.account.username:
        return
    subcategory = getattr(event.order, 'subcategory', None)
    if not subcategory or int(getattr(subcategory, 'id', 0) or 0) not in get_allowed_subcategory_ids():
        return
    chat = bot.account.get_chat_by_name(event.order.buyer_username, True)
    if not chat:
        return
    currency = extract_currency(getattr(event.order, 'html', None)) or 'RUB'
    quantity = extract_quantity(getattr(event.order, 'html', None)) or float(getattr(event.order, 'amount', 1) or 1)
    steam_login = extract_steam_login(getattr(event.order, 'html', None))
    service.set_state(chat.id, int(getattr(event.order, 'buyer_id', 0) or 0), {'state': 'waiting_for_steam_login' if not steam_login else 'confirming_login', 'data': {'order_id': str(event.order.id), 'currency': currency, 'quantity': quantity, 'steam_login': steam_login}})
    if steam_login:
        bot.send_message(chat.id, format_message(get_messages().get('confirm_login', ''), order_id=event.order.id, steam_login=steam_login, quantity=quantity, currency=currency))
    else:
        bot.send_message(chat.id, format_message(get_messages().get('ask_login', ''), order_id=event.order.id))


async def on_new_message(bot, event):
    if not is_enabled() or not is_owned():
        return
    if event.message.author_id == bot.account.id or event.message.author == bot.account.username:
        return

    if event.message.author_id == 0 and event.message.type and getattr(event.message.type, 'name', '') == 'ORDER_PURCHASED':
        order_id = extract_order_id_from_message(event.message.text)
        if order_id and (not is_order_verification_enabled() or _verify_order(bot, order_id)):
            try:
                order = bot.account.get_order(order_id)
                fake_event = type('E', (), {'order': order})
                return await on_new_order(bot, fake_event)
            except Exception:
                return

    state = service.get_state(event.message.chat_id, event.message.author_id)
    if not state or event.message.type is not MessageTypes.NON_SYSTEM:
        return

    text = (event.message.text or '').strip()
    data = dict(state.get('data') or {})
    order_id = str(data.get('order_id') or '')
    currency = str(data.get('currency') or 'RUB')
    quantity = float(data.get('quantity') or 1)

    try:
        order = bot.account.get_order(order_id)
        if getattr(order, 'status', None) in {OrderStatuses.CLOSED, OrderStatuses.REFUNDED}:
            service.set_state(event.message.chat_id, event.message.author_id, None)
            return
    except Exception:
        pass

    if state.get('state') == 'waiting_for_steam_login':
        if not is_valid_steam_login(text):
            bot.send_message(event.message.chat_id, get_messages().get('invalid_login', 'Неверный логин Steam.'))
            return
        if text.lower() in get_blacklist_logins():
            bot.send_message(event.message.chat_id, 'Этот Steam login находится в blacklist. Ожидайте продавца.')
            return
        service.set_state(event.message.chat_id, event.message.author_id, {'state': 'confirming_login', 'data': {**data, 'steam_login': text}})
        bot.send_message(event.message.chat_id, format_message(get_messages().get('confirm_login', ''), order_id=order_id, steam_login=text, quantity=quantity, currency=currency))
        return

    if state.get('state') == 'confirming_login':
        if text == '+':
            steam_login = str(data.get('steam_login') or '')
            position = service.enqueue(bot, order_id, event.message.chat_id, int(event.message.author_id), steam_login, currency, quantity)
            service.set_state(event.message.chat_id, event.message.author_id, {'state': 'processing', 'data': data})
            bot.send_message(event.message.chat_id, format_message(get_messages().get('queue_added', ''), position=position))
            return
        if is_valid_steam_login(text):
            if text.lower() in get_blacklist_logins():
                bot.send_message(event.message.chat_id, 'Этот Steam login находится в blacklist. Ожидайте продавца.')
                return
            service.set_state(event.message.chat_id, event.message.author_id, {'state': 'confirming_login', 'data': {**data, 'steam_login': text}})
            bot.send_message(event.message.chat_id, format_message(get_messages().get('confirm_login', ''), order_id=order_id, steam_login=text, quantity=quantity, currency=currency))
            return
        bot.send_message(event.message.chat_id, get_messages().get('reply_plus', 'Отправьте + или новый логин Steam.'))


FUNPAY_EVENT_HANDLERS = {EventTypes.NEW_ORDER: [on_new_order], EventTypes.NEW_MESSAGE: [on_new_message]}
