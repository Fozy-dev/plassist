from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

import aiohttp

from core.runtime_paths import resolve_runtime_path
from core.text_normalizer import normalize_data


API_BASE = "https://pay.crypt.bot/api"
PAYMENTS_PATH = "bot_data/cryptobot_payments.json"


class CryptoBotError(RuntimeError):
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


class CryptoBotClient:
    def __init__(self, api_token: str, timeout: int = 20):
        self.api_token = (api_token or "").strip()
        self.timeout = timeout
        if not self.api_token:
            raise CryptoBotError("API token CryptoBot не задан.")

    async def _request(self, method: str, payload: dict[str, Any] | None = None) -> dict:
        headers = {"Crypto-Pay-API-Token": self.api_token}
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            async with session.post(f"{API_BASE}/{method}", json=payload or {}) as response:
                raw = await response.text()
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError:
                    raise CryptoBotError(f"Некорректный ответ CryptoBot: {raw[:200]}")
                if response.status >= 400:
                    raise CryptoBotError(parsed.get("error", {}).get("name") or parsed.get("error") or f"HTTP {response.status}")
                if not parsed.get("ok"):
                    err = parsed.get("error")
                    if isinstance(err, dict):
                        desc = err.get("name") or err.get("code") or err.get("message")
                    else:
                        desc = str(err or "unknown error")
                    raise CryptoBotError(desc)
                return parsed.get("result") or {}

    async def create_invoice(self, *, amount_rub: float, description: str, paid_btn_url: str | None = None) -> dict:
        payload: dict[str, Any] = {
            "currency_type": "fiat",
            "fiat": "RUB",
            "amount": f"{amount_rub:.2f}",
            "description": description[:1024],
        }
        if paid_btn_url:
            payload["paid_btn_name"] = "openBot"
            payload["paid_btn_url"] = paid_btn_url
        return await self._request("createInvoice", payload)

    async def get_invoice(self, *, invoice_id: int) -> dict | None:
        result = await self._request("getInvoices", {"invoice_ids": str(invoice_id)})
        items = result.get("items") or []
        if not items:
            return None
        return items[0]

    @staticmethod
    def is_paid(invoice: dict | None) -> bool:
        if not invoice:
            return False
        return str(invoice.get("status", "")).lower() == "paid"


class CryptoLedger:
    @staticmethod
    def all() -> dict[str, dict]:
        return _read_json(PAYMENTS_PATH, {})

    @staticmethod
    def get(payment_id: str) -> dict | None:
        return CryptoLedger.all().get(payment_id)

    @staticmethod
    def create(*, payment_id: str, user_id: int, amount: float, invoice_id: int, pay_url: str) -> dict:
        payload = CryptoLedger.all()
        now = datetime.now().isoformat(timespec="seconds")
        payload[payment_id] = {
            "payment_id": payment_id,
            "user_id": int(user_id),
            "amount": round(float(amount), 2),
            "invoice_id": int(invoice_id),
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
        payload = CryptoLedger.all()
        row = payload.get(payment_id)
        if not row:
            return None
        now = datetime.now().isoformat(timespec="seconds")
        row["status"] = "paid"
        row["paid_at"] = row.get("paid_at") or now
        row["updated_at"] = now
        if invoice:
            row["raw_invoice"] = invoice
        payload[payment_id] = row
        _write_json(PAYMENTS_PATH, payload)
        return row

    @staticmethod
    def mark_credited(payment_id: str) -> dict | None:
        payload = CryptoLedger.all()
        row = payload.get(payment_id)
        if not row:
            return None
        row["credited"] = True
        row["updated_at"] = datetime.now().isoformat(timespec="seconds")
        payload[payment_id] = row
        _write_json(PAYMENTS_PATH, payload)
        return row
