from __future__ import annotations

import asyncio
import base64
import logging
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
import requests

from tgbot.telegrambot import get_telegram_bot

from .helpers import blur_name, format_message
from .storage import (
    get_config,
    get_allowed_quantities,
    get_fragment_config,
    get_messages,
    get_ton_config,
    mark_completed,
    update_pending_order,
    update_stats,
)


logger = logging.getLogger("universal.auto_stars")


def _decoder(data: str) -> bytes:
    while len(data) % 4 != 0:
        data += "="
    return base64.b64decode(data)


def _extract_ref_id(data: bytes) -> str:
    decoded_data = data.decode("latin1")
    return decoded_data.split("Ref#")[-1]


def _to_nano(amount: float | str | Decimal) -> int:
    return int((Decimal(str(amount)) * Decimal("1000000000")).quantize(Decimal("1")))


class AutoStarsService:
    def __init__(self):
        self.queue: asyncio.Queue[tuple[Any, int, str, int, str]] = asyncio.Queue()
        self.worker_task: asyncio.Task | None = None

    def start(self):
        if self.worker_task and not self.worker_task.done():
            return
        self.worker_task = asyncio.create_task(self._worker())

    def enqueue(self, bot, buyer_chat_id: int, username: str, quantity: int, order_id: str | int) -> int:
        self.start()
        self.queue.put_nowait((bot, buyer_chat_id, username, quantity, str(order_id)))
        return self.queue.qsize()

    async def _worker(self):
        while True:
            bot, buyer_chat_id, username, quantity, order_id = await self.queue.get()
            try:
                await self.process_payment(bot, buyer_chat_id, username, quantity, order_id)
            except Exception as exc:
                logger.exception("AutoStars queue worker failed: %s", exc)
            finally:
                self.queue.task_done()

    async def _notify_admins(self, text: str):
        telegram = get_telegram_bot()
        if not telegram:
            return
        signed_users = (
            (telegram.config or {}).get("telegram", {}).get("bot", {}).get("signed_users", []) or []
        )
        for user_id in signed_users:
            try:
                await telegram.bot.send_message(chat_id=user_id, text=text)
            except Exception:
                continue

    async def search_recipient_preview(self, username: str, quantity: int = 50) -> dict[str, str]:
        fragment = get_fragment_config()
        url = (fragment.get("url") or "").strip()
        hash_value = (fragment.get("hash") or "").strip()
        cookie = (fragment.get("cookie") or "").strip()
        if not (url and hash_value and cookie):
            return {"preview_name": "Не настроено", "recipient_id": "Не настроено"}
        headers = {
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Cookie": cookie,
            "Origin": "https://fragment.com",
            "Referer": "https://fragment.com/stars/buy",
            "User-Agent": "Mozilla/5.0",
            "X-Requested-With": "XMLHttpRequest",
        }
        payload = {
            "query": username.lstrip("@"),
            "quantity": quantity,
            "method": "searchStarsRecipient",
        }

        def _request():
            return requests.post(f"{url}?hash={hash_value}", headers=headers, data=payload, timeout=30)

        response = await asyncio.to_thread(_request)
        response.raise_for_status()
        data = response.json()
        if not data.get("ok"):
            return {"preview_name": "Не найдено", "recipient_id": "Не найдено"}
        found = data.get("found") or {}
        return {
            "preview_name": blur_name(found.get("name")),
            "recipient_id": str(found.get("recipient") or "Не найдено"),
        }

    def is_configured(self) -> bool:
        fragment = get_fragment_config()
        ton = get_ton_config()
        return all(
            [
                fragment.get("url"),
                fragment.get("hash"),
                fragment.get("cookie"),
                ton.get("api_key"),
                ton.get("destination_address"),
                len(ton.get("mnemonic") or []) == 24,
            ]
        )

    async def _create_wallet(self):
        try:
            from tonutils.clients.http.clients.tonapi import TonapiClient
            from tonutils.contracts.wallet import WalletV4R2
            from tonutils.types import NetworkGlobalID
        except ImportError as exc:
            raise RuntimeError(f"Не удалось импортировать tonutils: {exc}") from exc

        ton = get_ton_config()
        network = NetworkGlobalID.TESTNET if bool(ton.get("is_testnet")) else NetworkGlobalID.MAINNET
        client = TonapiClient(network, api_key=ton.get("api_key"), timeout=20.0)
        wallet, _, _, _ = WalletV4R2.from_mnemonic(client, ton.get("mnemonic") or [])
        await wallet.refresh()
        return wallet

    async def check_wallet_balance(self) -> float:
        wallet = await self._create_wallet()
        return wallet.balance / 1_000_000_000

    async def send_ton_transaction(self, amount: float, comment: str):
        balance = await self.check_wallet_balance()
        if balance < amount:
            return None, None, format_message(get_messages().get("insufficient_balance", ""), amount=amount, balance=balance)
        ton = get_ton_config()
        wallet = await self._create_wallet()
        try:
            amount_nano = _to_nano(amount)
        except (InvalidOperation, ValueError) as exc:
            return None, None, f"Некорректная сумма для TON-транзакции: {amount}. ({exc})"
        external_message = await wallet.transfer(
            destination=ton.get("destination_address"),
            amount=amount_nano,
            body=comment,
        )
        ref_id = comment.split("Ref#")[-1].strip()
        return external_message.normalized_hash, ref_id, None

    async def _fragment_buy(self, username: str, quantity: int):
        fragment = get_fragment_config()
        url = (fragment.get("url") or "").strip()
        hash_value = (fragment.get("hash") or "").strip()
        cookie = (fragment.get("cookie") or "").strip()
        if not (url and hash_value and cookie):
            return None, None, quantity, get_messages().get("not_configured", "Модуль не настроен.")

        headers = {
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Cookie": cookie,
            "Origin": "https://fragment.com",
            "Referer": "https://fragment.com/stars/buy",
            "User-Agent": "Mozilla/5.0",
            "X-Requested-With": "XMLHttpRequest",
        }
        base_url = f"{url}?hash={hash_value}"

        def _post(payload: dict):
            response = requests.post(base_url, headers=headers, data=payload, timeout=30)
            response.raise_for_status()
            return response.json()

        search_data = await asyncio.to_thread(
            _post,
            {"query": username.lstrip("@"), "quantity": quantity, "method": "searchStarsRecipient"},
        )
        if not search_data.get("ok"):
            return None, None, quantity, str(search_data.get("error") or "Не удалось найти Telegram username.")

        recipient = (search_data.get("found") or {}).get("recipient")
        init_data = await asyncio.to_thread(
            _post,
            {"recipient": recipient, "quantity": quantity, "method": "initBuyStarsRequest"},
        )
        req_id = init_data.get("req_id")
        amount = float(init_data.get("amount") or 0)
        if not req_id or amount <= 0:
            return None, None, quantity, "Fragment не вернул req_id или сумму для покупки."

        link_data = await asyncio.to_thread(
            _post,
            {
                "transaction": "1",
                "id": req_id,
                "show_sender": str(get_config().get("show_sender") or "0"),
                "method": "getBuyStarsLink",
            },
        )
        if not link_data.get("ok"):
            return None, None, quantity, str(link_data.get("error") or "Не удалось получить ссылку на покупку Stars.")

        messages = ((link_data.get("transaction") or {}).get("messages") or [])
        if not messages:
            return None, None, quantity, "Fragment не вернул payload транзакции."
        payload_transaction = messages[0].get("payload")
        if not payload_transaction:
            return None, None, quantity, "Fragment вернул пустой payload транзакции."
        ref_id = _extract_ref_id(_decoder(payload_transaction))
        comment = f"{quantity} Telegram Stars\n\nRef#{ref_id}"
        tx_hash, _, error = await self.send_ton_transaction(amount, comment)
        if error:
            return None, None, quantity, error
        return tx_hash, ref_id, quantity, None

    async def confirm_transaction(self, tx_hash: str) -> bool:
        async with httpx.AsyncClient(timeout=20) as client:
            for _ in range(15):
                try:
                    response = await client.get(
                        "https://preview.toncenter.com/api/v3/traces",
                        params={"msg_hash": tx_hash, "include_actions": "true"},
                    )
                    data = response.json()
                    traces = data.get("traces") or []
                    for trace in traces:
                        for action in trace.get("actions") or []:
                            if action.get("success"):
                                return True
                except Exception:
                    pass
                await asyncio.sleep(4)
        return False

    async def process_payment(self, bot, buyer_chat_id: int, username: str, quantity: int, order_id: str):
        messages = get_messages()
        if quantity not in get_allowed_quantities():
            error = f"Недопустимое количество Stars: {quantity}."
            bot.send_message(buyer_chat_id, format_message(messages.get("payment_failed", ""), error=error))
            if get_config().get("auto_refund"):
                try:
                    bot.account.refund(order_id)
                except Exception:
                    pass
            update_stats(False, quantity)
            mark_completed(buyer_chat_id, order_id, completed=False, cancelled=False)
            return
        tx_hash, ref_id, quantity, error = await self._fragment_buy(username, quantity)
        if error:
            bot.send_message(buyer_chat_id, format_message(messages.get("payment_failed", ""), error=error))
            if get_config().get("auto_refund"):
                try:
                    bot.account.refund(order_id)
                except Exception:
                    pass
            update_stats(False, quantity)
            mark_completed(buyer_chat_id, order_id, completed=False, cancelled=False)
            await self._notify_admins(f"AutoStars: ошибка по заказу {order_id}: {error}")
            return

        confirmed = await self.confirm_transaction(tx_hash)
        if not confirmed:
            error = "Не удалось подтвердить транзакцию в сети TON."
            bot.send_message(buyer_chat_id, format_message(messages.get("payment_failed", ""), error=error))
            if get_config().get("auto_refund"):
                try:
                    bot.account.refund(order_id)
                except Exception:
                    pass
            update_stats(False, quantity)
            mark_completed(buyer_chat_id, order_id, completed=False, cancelled=False)
            await self._notify_admins(f"AutoStars: транзакция {tx_hash} не подтвердилась для заказа {order_id}.")
            return

        bot.send_message(
            buyer_chat_id,
            format_message(
                messages.get("completed", ""),
                quantity=quantity,
                ref_id=ref_id,
                ton_viewer_url=f"https://tonviewer.com/transaction/{tx_hash}",
            ),
        )
        update_stats(True, quantity)
        update_pending_order(buyer_chat_id, order_id, tx_hash=tx_hash, ref_id=ref_id, completed=True)
        await self._notify_admins(f"AutoStars: заказ {order_id} выполнен, {quantity} Stars, Ref#{ref_id}.")


service = AutoStarsService()
