from __future__ import annotations

import json
import os
import secrets
import time
from datetime import datetime
from typing import Any

import aiohttp

from core.runtime_paths import resolve_runtime_path
from core.text_normalizer import normalize_data


API_BASE = "https://api.lava.ru/business"
PAYMENTS_PATH = "bot_data/lava_payments.json"


class LavaError(RuntimeError):
    pass


def _read_json(path: str, default):
    path = resolve_runtime_path(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        with open(path, "r", encoding="utf-8") as file:
            payload = json.load(file)
        normalized = normalize_data(payload)
        if normalized != payload:
            with open(path, "w", encoding="utf-8") as file:
                json.dump(normalized, file, ensure_ascii=False, indent=4)
        return normalized
    except Exception:
        normalized_default = normalize_data(default)
        with open(path, "w", encoding="utf-8") as file:
            json.dump(normalized_default, file, ensure_ascii=False, indent=4)
        return normalized_default


def _write_json(path: str, payload):
    path = resolve_runtime_path(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    normalized_payload = normalize_data(payload)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(normalized_payload, file, ensure_ascii=False, indent=4)


class LavaClient:
    def __init__(self, *, signature: str, timeout: int = 20):
        self.signature = (signature or "").strip()
        self.timeout = int(timeout or 20)
        if not self.signature:
            raise LavaError("Не задан Signature для LAVA.")

    async def _request(self, endpoint: str, payload: dict[str, Any]) -> dict:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Signature": self.signature,
        }
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        url = f"{API_BASE}/{endpoint.lstrip('/')}"
        async with aiohttp.ClientSession(timeout=timeout) as session:
            try:
                async with session.post(url, headers=headers, json=payload) as response:
                    raw = await response.text()
                    try:
                        parsed = json.loads(raw)
                    except json.JSONDecodeError:
                        raise LavaError(f"LAVA вернула не-JSON ответ: {raw[:300]}") from None
                    if response.status >= 400:
                        raise LavaError(f"HTTP {response.status}: {parsed.get('error') or parsed}")
                    if not parsed.get("status_check", False):
                        raise LavaError(str(parsed.get("error") or parsed))
                    return parsed
            except aiohttp.ClientError as e:
                raise LavaError(f"Ошибка соединения с LAVA: {e}") from e

    async def create_invoice(
        self,
        *,
        amount_rub: float,
        order_id: str,
        shop_id: str,
        comment: str | None = None,
    ) -> dict:
        payload: dict[str, Any] = {
            "shopId": str(shop_id),
            "sum": round(float(amount_rub), 2),
            "orderId": str(order_id),
        }
        if comment:
            payload["comment"] = str(comment)
        return await self._request("invoice/create", payload)

    async def invoice_status(
        self,
        *,
        shop_id: str,
        order_id: str | None = None,
        invoice_id: str | None = None,
    ) -> dict:
        payload: dict[str, Any] = {"shopId": str(shop_id)}
        if order_id:
            payload["orderId"] = str(order_id)
        if invoice_id:
            payload["invoiceId"] = str(invoice_id)
        if not order_id and not invoice_id:
            raise LavaError("Для проверки LAVA нужен orderId или invoiceId.")
        return await self._request("invoice/status", payload)

    @staticmethod
    def is_paid(invoice: dict | None) -> bool:
        if not invoice:
            return False
        status = str(invoice.get("status") or "").lower()
        return status in {"success", "paid", "completed", "done"}


class LavaLedger:
    @staticmethod
    def all() -> dict[str, dict]:
        return _read_json(PAYMENTS_PATH, {})

    @staticmethod
    def get(payment_id: str) -> dict | None:
        return LavaLedger.all().get(payment_id)

    @staticmethod
    def make_payment_id(user_id: int) -> str:
        return f"lv{int(user_id)}_{int(time.time())}_{secrets.token_hex(4)}"

    @staticmethod
    def create(
        *,
        payment_id: str,
        user_id: int,
        amount: float,
        shop_id: str,
        order_id: str,
        invoice_id: str | None,
        pay_url: str,
    ) -> dict:
        payload = LavaLedger.all()
        now = datetime.now().isoformat(timespec="seconds")
        payload[payment_id] = {
            "payment_id": payment_id,
            "user_id": int(user_id),
            "amount": round(float(amount), 2),
            "shop_id": str(shop_id),
            "order_id": str(order_id),
            "invoice_id": invoice_id,
            "pay_url": pay_url,
            "status": "new",
            "credited": False,
            "created_at": now,
            "updated_at": now,
            "paid_at": None,
            "raw_invoice": {},
        }
        _write_json(PAYMENTS_PATH, payload)
        return payload[payment_id]

    @staticmethod
    def mark_paid(payment_id: str, invoice: dict | None = None) -> dict | None:
        payload = LavaLedger.all()
        row = payload.get(payment_id)
        if not row:
            return None
        now = datetime.now().isoformat(timespec="seconds")
        row["status"] = "paid"
        row["paid_at"] = row.get("paid_at") or now
        row["updated_at"] = now
        if invoice:
            row["raw_invoice"] = invoice
            inv_id = invoice.get("id")
            if inv_id:
                row["invoice_id"] = str(inv_id)
        payload[payment_id] = row
        _write_json(PAYMENTS_PATH, payload)
        return row

    @staticmethod
    def mark_credited(payment_id: str) -> dict | None:
        payload = LavaLedger.all()
        row = payload.get(payment_id)
        if not row:
            return None
        row["credited"] = True
        row["updated_at"] = datetime.now().isoformat(timespec="seconds")
        payload[payment_id] = row
        _write_json(PAYMENTS_PATH, payload)
        return row
