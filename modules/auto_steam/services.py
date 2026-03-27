from __future__ import annotations

import threading
import time
import uuid
from queue import Queue

import requests

from .helpers import format_message
from .storage import (
    add_history,
    get_api_login,
    get_api_password,
    get_messages,
    get_reminder_time_minutes,
    is_auto_refund_enabled,
    is_confirmation_reminder_enabled,
)


class AutoSteamService:
    def __init__(self):
        self.token_data = {"token": None, "expiry": 0.0}
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

    def get_token(self) -> str:
        if time.time() < self.token_data["expiry"] and self.token_data["token"]:
            return str(self.token_data["token"])
        payload = {"email": get_api_login(), "password": get_api_password()}
        if not payload["email"] or not payload["password"]:
            raise RuntimeError("Не заполнены api_login / api_password")
        response = requests.post("https://api.ns.gifts/api/v1/get_token", json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        token = data.get("token") or data.get("access_token") or ((data.get("data") or {}).get("token"))
        if not token:
            raise RuntimeError("NSGifts не вернул token")
        self.token_data["token"] = token
        self.token_data["expiry"] = float(data.get("valid_thru") or (time.time() + 7200))
        return str(token)

    def get_balance(self) -> float | None:
        try:
            token = self.get_token()
            response = requests.post("https://api.ns.gifts/api/v1/check_balance", headers={"Authorization": f"Bearer {token}"}, timeout=30)
            response.raise_for_status()
            data = response.json()
            if isinstance(data, (int, float)):
                return float(data)
            return float(data.get("balance", 0))
        except Exception:
            return None

    def get_currency_rates(self) -> dict:
        token = self.get_token()
        response = requests.post(
            "https://api.ns.gifts/api/v1/steam/get_currency_rate",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def create_order(self, amount_usd: float, steam_login: str) -> str:
        token = self.get_token()
        custom_id = str(uuid.uuid4())
        response = requests.post(
            "https://api.ns.gifts/api/v1/create_order",
            json={"service_id": 1, "quantity": f"{amount_usd:.2f}", "custom_id": custom_id, "data": steam_login},
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        if response.status_code == 400 and "There is no such login" in response.text:
            raise RuntimeError("InvalidLogin")
        response.raise_for_status()
        return custom_id

    def pay_order(self, custom_id: str):
        token = self.get_token()
        response = requests.post(
            "https://api.ns.gifts/api/v1/pay_order",
            json={"custom_id": custom_id},
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        if response.status_code >= 400:
            try:
                detail = (response.json() or {}).get("detail", response.text)
            except Exception:
                detail = response.text
            if "Недостаточно средств" in str(detail):
                raise RuntimeError("InsufficientFunds")
            raise RuntimeError(str(detail))
        return True

    def enqueue(self, bot, order_id: str, chat_id: int | str, buyer_id: int, steam_login: str, currency: str, quantity: float) -> int:
        queue = self.user_order_queues.setdefault(int(buyer_id), Queue())
        queue.put({"order_id": str(order_id), "chat_id": chat_id, "buyer_id": int(buyer_id), "steam_login": steam_login, "currency": currency, "quantity": float(quantity), "bot": bot})
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
                self._process_topup(**item)
            finally:
                queue.task_done()
        self.user_order_queues.pop(int(buyer_id), None)

    def _process_topup(self, bot, order_id: str, chat_id, buyer_id: int, steam_login: str, currency: str, quantity: float):
        messages = get_messages()
        try:
            rates = self.get_currency_rates()
            rate_key = f"{currency.lower()}/usd"
            rate = float(rates.get(rate_key, 0) or 0)
            if rate <= 0:
                raise RuntimeError(f"Не найден курс для {currency}")
            amount_usd = round(float(quantity) / rate, 2)
            custom_id = self.create_order(amount_usd, steam_login)
            self.pay_order(custom_id)
            bot.send_message(chat_id, format_message(messages.get("success", ""), steam_login=steam_login, quantity=quantity, currency=currency, order_id=order_id))
            add_history({"order_id": order_id, "steam_login": steam_login, "quantity": quantity, "currency": currency, "status": "success", "timestamp": time.time(), "buyer_id": buyer_id})
            self._notify_admins(bot, format_message(messages.get("admin_log", ""), order_id=order_id, steam_login=steam_login, quantity=quantity, currency=currency))
            if is_confirmation_reminder_enabled():
                threading.Thread(target=self._confirmation_reminder, args=(bot, order_id, chat_id), daemon=True).start()
        except Exception as exc:
            self._notify_admins(bot, format_message(messages.get("admin_error", ""), order_id=order_id, error=str(exc)))
            if str(exc) == "InvalidLogin":
                self.set_state(chat_id, buyer_id, {"state": "waiting_for_steam_login", "data": {"order_id": order_id}})
                bot.send_message(chat_id, messages.get("invalid_login", "Неверный логин Steam."))
                return
            if is_auto_refund_enabled():
                try:
                    bot.account.refund(order_id)
                    bot.send_message(chat_id, messages.get("refund", "Средства возвращены."))
                except Exception:
                    pass
            add_history({"order_id": order_id, "steam_login": steam_login, "quantity": quantity, "currency": currency, "status": f"error: {exc}", "timestamp": time.time(), "buyer_id": buyer_id})
        finally:
            self.set_state(chat_id, buyer_id, None)

    def _confirmation_reminder(self, bot, order_id: str, chat_id):
        time.sleep(int(get_reminder_time_minutes() * 60))
        try:
            order = bot.account.get_order(order_id)
            if getattr(order, "status", None).name not in {"CLOSED", "REFUNDED"}:
                bot.send_message(chat_id, format_message(get_messages().get("reminder", ""), order_id=order_id))
        except Exception:
            pass

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


service = AutoSteamService()
