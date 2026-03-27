from __future__ import annotations

import threading
import time
from queue import Queue
from urllib.parse import quote_plus

import requests

from .helpers import format_message
from .storage import add_history, get_api_key, get_api_url, get_messages, is_auto_refund_enabled


class AutoSmmService:
    def __init__(self):
        self.pending_states: dict[tuple, dict] = {}
        self.user_order_queues: dict[int, Queue] = {}

    def get_state(self, chat_id: int | str, author_id: int):
        return self.pending_states.get((chat_id, author_id))

    def set_state(self, chat_id: int | str, author_id: int, value: dict | None):
        key = (chat_id, author_id)
        if value is None:
            self.pending_states.pop(key, None)
        else:
            self.pending_states[key] = value

    def get_balance(self) -> float | None:
        try:
            response = requests.get(f"{get_api_url()}?action=balance&key={get_api_key()}", timeout=30)
            response.raise_for_status()
            data = response.json()
            if isinstance(data, dict):
                return float(data.get("balance", 0))
            return float(data)
        except Exception:
            return None

    def create_order(self, service_id: int, link: str, quantity: int) -> str:
        if not get_api_url() or not get_api_key():
            raise RuntimeError("Не заполнены api_url / api_key")
        url = f"{get_api_url()}?action=add&service={int(service_id)}&link={quote_plus(link)}&quantity={int(quantity)}&key={quote_plus(get_api_key())}"
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict):
            if data.get("error"):
                raise RuntimeError(str(data.get("error")))
            order_id = data.get("order")
            if order_id:
                return str(order_id)
        if isinstance(data, (int, float, str)) and str(data).strip().isdigit():
            return str(data).strip()
        raise RuntimeError(f"Некорректный ответ API: {data}")

    def enqueue(self, bot, order_id: str, chat_id: int | str, buyer_id: int, link: str, service_id: int, quantity: int) -> int:
        queue = self.user_order_queues.setdefault(int(buyer_id), Queue())
        queue.put({"order_id": str(order_id), "chat_id": chat_id, "buyer_id": int(buyer_id), "link": link, "service_id": int(service_id), "quantity": int(quantity), "bot": bot})
        position = queue.qsize()
        if position == 1:
            threading.Thread(target=self._process_user_queue, args=(int(buyer_id),), daemon=True).start()
        return position

    def _process_user_queue(self, buyer_id: int):
        queue = self.user_order_queues.get(int(buyer_id))
        if not queue:
            return
        while not queue.empty():
            item = queue.get()
            try:
                self._process_order(**item)
            finally:
                queue.task_done()
        self.user_order_queues.pop(int(buyer_id), None)

    def _process_order(self, bot, order_id: str, chat_id, buyer_id: int, link: str, service_id: int, quantity: int):
        messages = get_messages()
        try:
            service_order_id = self.create_order(service_id, link, quantity)
            bot.send_message(chat_id, format_message(messages.get("after_confirmation", ""), order_id=order_id, link=link, service_order_id=service_order_id))
            add_history({"order_id": order_id, "buyer_id": buyer_id, "link": link, "service_id": service_id, "quantity": quantity, "service_order_id": service_order_id, "status": "success", "timestamp": time.time()})
            self._notify_admins(bot, format_message(messages.get("admin_log", ""), order_id=order_id, link=link, service_order_id=service_order_id))
        except Exception as exc:
            self._notify_admins(bot, format_message(messages.get("admin_error", ""), order_id=order_id, error=str(exc)))
            if is_auto_refund_enabled():
                try:
                    bot.account.refund(order_id)
                    bot.send_message(chat_id, messages.get("refund", "Средства возвращены."))
                except Exception:
                    pass
            add_history({"order_id": order_id, "buyer_id": buyer_id, "link": link, "service_id": service_id, "quantity": quantity, "status": f"error: {exc}", "timestamp": time.time()})
        finally:
            self.set_state(chat_id, buyer_id, None)

    def _notify_admins(self, bot, text: str):
        from tgbot.telegrambot import get_telegram_bot

        telegram = get_telegram_bot()
        if not telegram:
            return
        signed = ((telegram.config or {}).get("telegram", {}).get("bot", {}).get("signed_users", []) or [])
        for user_id in signed:
            try:
                telegram.loop.create_task(telegram.bot.send_message(chat_id=user_id, text=text))
            except Exception:
                continue


service = AutoSmmService()
