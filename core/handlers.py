from __future__ import annotations

from logging import getLogger

from colorama import Fore
from playerokapi.listener.events import EventTypes as PlayerokEventTypes

try:
    from FunPayAPI.updater.events import EventTypes as FunPayEventTypes
except Exception:
    FunPayEventTypes = None


logger = getLogger("universal.handlers")

_bot_event_handlers: dict[str, list[callable]] = {
    "ON_MODULE_CONNECTED": [],
    "ON_MODULE_ENABLED": [],
    "ON_INIT": [],
    "ON_PLAYEROK_BOT_INIT": [],
    "ON_FUNPAY_BOT_INIT": [],
    "ON_TELEGRAM_BOT_INIT": [],
}

_playerok_event_handlers: dict[PlayerokEventTypes, list[callable]] = {
    PlayerokEventTypes.CHAT_INITIALIZED: [],
    PlayerokEventTypes.NEW_MESSAGE: [],
    PlayerokEventTypes.NEW_DEAL: [],
    PlayerokEventTypes.NEW_REVIEW: [],
    PlayerokEventTypes.DEAL_CONFIRMED: [],
    PlayerokEventTypes.DEAL_CONFIRMED_AUTOMATICALLY: [],
    PlayerokEventTypes.DEAL_ROLLED_BACK: [],
    PlayerokEventTypes.DEAL_HAS_PROBLEM: [],
    PlayerokEventTypes.DEAL_PROBLEM_RESOLVED: [],
    PlayerokEventTypes.DEAL_STATUS_CHANGED: [],
    PlayerokEventTypes.ITEM_PAID: [],
    PlayerokEventTypes.ITEM_SENT: [],
}

_funpay_event_handlers: dict = {}
if FunPayEventTypes is not None:
    _funpay_event_handlers = {
        FunPayEventTypes.INITIAL_CHAT: [],
        FunPayEventTypes.INITIAL_ORDER: [],
        FunPayEventTypes.CHATS_LIST_CHANGED: [],
        FunPayEventTypes.ORDERS_LIST_CHANGED: [],
        FunPayEventTypes.LAST_CHAT_MESSAGE_CHANGED: [],
        FunPayEventTypes.NEW_MESSAGE: [],
        FunPayEventTypes.NEW_ORDER: [],
        FunPayEventTypes.ORDER_STATUS_CHANGED: [],
    }


def get_bot_event_handlers() -> dict[str, list[callable]]:
    return _bot_event_handlers


def set_bot_event_handlers(data: dict[str, list[callable]]):
    global _bot_event_handlers
    _bot_event_handlers = data


def add_bot_event_handler(event: str, handler: callable, index: int | None = None):
    global _bot_event_handlers
    if event not in _bot_event_handlers:
        _bot_event_handlers[event] = []
    if index is None:
        _bot_event_handlers[event].append(handler)
    else:
        _bot_event_handlers[event].insert(index, handler)


def register_bot_event_handlers(handlers: dict[str, list[callable]]):
    global _bot_event_handlers
    for event_type, funcs in handlers.items():
        if event_type not in _bot_event_handlers:
            _bot_event_handlers[event_type] = []
        _bot_event_handlers[event_type].extend(funcs)


def remove_bot_event_handlers(handlers: dict[str, list[callable]]):
    global _bot_event_handlers
    for event, funcs in handlers.items():
        if event in _bot_event_handlers:
            for func in funcs:
                if func in _bot_event_handlers[event]:
                    _bot_event_handlers[event].remove(func)


def get_playerok_event_handlers() -> dict[PlayerokEventTypes, list[callable]]:
    return _playerok_event_handlers


def set_playerok_event_handlers(data: dict[PlayerokEventTypes, list[callable]]):
    global _playerok_event_handlers
    _playerok_event_handlers = data


def add_playerok_event_handler(
    event: PlayerokEventTypes,
    handler: callable,
    index: int | None = None,
):
    global _playerok_event_handlers
    if event not in _playerok_event_handlers:
        _playerok_event_handlers[event] = []
    if index is None:
        _playerok_event_handlers[event].append(handler)
    else:
        _playerok_event_handlers[event].insert(index, handler)


def register_playerok_event_handlers(handlers: dict[PlayerokEventTypes, list[callable]]):
    global _playerok_event_handlers
    for event_type, funcs in handlers.items():
        if event_type not in _playerok_event_handlers:
            _playerok_event_handlers[event_type] = []
        _playerok_event_handlers[event_type].extend(funcs)


def remove_playerok_event_handlers(handlers: dict[PlayerokEventTypes, list[callable]]):
    global _playerok_event_handlers
    for event, funcs in handlers.items():
        if event in _playerok_event_handlers:
            for func in funcs:
                if func in _playerok_event_handlers[event]:
                    _playerok_event_handlers[event].remove(func)


def get_funpay_event_handlers() -> dict:
    return _funpay_event_handlers


def set_funpay_event_handlers(data: dict):
    global _funpay_event_handlers
    _funpay_event_handlers = data


def add_funpay_event_handler(event, handler: callable, index: int | None = None):
    global _funpay_event_handlers
    if event not in _funpay_event_handlers:
        _funpay_event_handlers[event] = []
    if index is None:
        _funpay_event_handlers[event].append(handler)
    else:
        _funpay_event_handlers[event].insert(index, handler)


def register_funpay_event_handlers(handlers: dict):
    global _funpay_event_handlers
    for event_type, funcs in handlers.items():
        if event_type not in _funpay_event_handlers:
            _funpay_event_handlers[event_type] = []
        _funpay_event_handlers[event_type].extend(funcs)


def remove_funpay_event_handlers(handlers: dict):
    global _funpay_event_handlers
    for event, funcs in handlers.items():
        if event in _funpay_event_handlers:
            for func in funcs:
                if func in _funpay_event_handlers[event]:
                    _funpay_event_handlers[event].remove(func)


async def call_bot_event(event: str, args: list | None = None, func=None):
    handlers = [func] if func else get_bot_event_handlers().get(event, [])
    for handler in handlers:
        try:
            await handler(*(args or []))
        except Exception as e:
            logger.error(
                f"{Fore.LIGHTRED_EX}Ошибка обработчика «{handler.__module__}.{handler.__qualname__}» "
                f"для события бота «{event}»: {Fore.WHITE}{e}"
            )


async def call_playerok_event(event: PlayerokEventTypes, args: list | None = None):
    handlers = get_playerok_event_handlers().get(event, [])
    for handler in handlers:
        try:
            await handler(*(args or []))
        except Exception as e:
            logger.error(
                f"{Fore.LIGHTRED_EX}Ошибка обработчика «{handler.__module__}.{handler.__qualname__}» "
                f"для события Playerok «{event.name}»: {Fore.WHITE}{e}"
            )


async def call_funpay_event(event, args: list | None = None):
    handlers = get_funpay_event_handlers().get(event, [])
    for handler in handlers:
        try:
            await handler(*(args or []))
        except Exception as e:
            event_name = getattr(event, "name", str(event))
            logger.error(
                f"{Fore.LIGHTRED_EX}Ошибка обработчика «{handler.__module__}.{handler.__qualname__}» "
                f"для события FunPay «{event_name}»: {Fore.WHITE}{e}"
            )
